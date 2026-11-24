"""Independent official-source date and close checks for the morning brief."""
from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from io import StringIO
import json
import re
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    NY = ZoneInfo("America/New_York")
except ZoneInfoNotFoundError:
    NY = None  # Windows without tzdata; reviewed years below use current US law
TW = timezone(timedelta(hours=8), "Asia/Taipei")
NYSE = "https://www.nyse.com/trade/hours-calendars"
TWSE_CAL = "https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&date={year}0101"
TWSE_CLOSE = "https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST?response=json&date={year}{month:02}01"
FRED_CLOSE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500&cosd={day}&coed={day}"

# NYSE's published 2026–28 calendar; intentionally fail beyond the reviewed range.
NY_CLOSED = {
    2026: "01-01 01-19 02-16 04-03 05-25 06-19 07-03 09-07 11-26 12-25",
    2027: "01-01 01-18 02-15 03-26 05-31 06-18 07-05 09-06 11-25 12-24",
    2028: "01-17 02-21 04-14 05-29 06-19 07-04 09-04 11-23 12-25",
}
NY_EARLY = {
    2026: "11-27 12-24",
    2027: "11-26",
    2028: "07-03 11-24",
}

class SourceError(ValueError):
    """A required source could not confirm the expected completed session."""

def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (research date validation)",
                                "Accept": "application/json,text/csv,text/plain,*/*"})
    try:
        with urlopen(req, timeout=20) as response:
            expected, actual = urlsplit(url), urlsplit(response.geturl())
            if actual.scheme != "https" or actual.hostname != expected.hostname:
                raise SourceError("Official source redirected to a different origin")
            result = response.read(4_000_001)
            if len(result) > 4_000_000:
                raise SourceError("Official source response too large")
            return result.decode("utf-8-sig")
    except (URLError, OSError, UnicodeError) as exc:
        raise SourceError(f"Official source unavailable: {urlsplit(url).hostname}") from exc

def nyse_close(day: date) -> time | None:
    if day.year not in NY_CLOSED:
        raise SourceError("NYSE calendar needs official annual update")
    mmdd = day.strftime("%m-%d")
    if day.weekday() >= 5 or mmdd in NY_CLOSED[day.year].split():
        return None
    return time(13) if mmdd in NY_EARLY[day.year].split() else time(16)

def parse_day(value: str) -> date:
    # TWSE publishes Gregorian holidays and ROC-index series dates.
    value = value.strip()
    match = re.fullmatch(r"(\d{2,4})[/-](\d{1,2})[/-](\d{1,2})", value)
    if not match:
        raise SourceError("Unrecognized TWSE date")
    y, m, d = map(int, match.groups())
    return date(y + 1911 if y < 1911 else y, m, d)

def twse_closed(payload: str, year: int) -> set[date]:
    obj = json.loads(payload)
    if str(obj.get("stat", "")).lower() != "ok":
        raise SourceError("TWSE calendar not OK")
    # The 'date' is the source's annual edition, not a trading-date assertion.
    if str(obj.get("date", "")) != f"{year}0101" or len(obj.get("data", [])) < 8:
        raise SourceError("TWSE calendar edition missing or incomplete")
    fields = obj.get("fields", [])
    if not all(key in fields for key in ("日期", "名稱", "說明")):
        raise SourceError("TWSE calendar field shape changed")
    indexes = [fields.index(key) for key in ("日期", "名稱", "說明")]
    closed = set()
    for row in obj["data"]:
        raw_date, label, desc = (row[i] for i in indexes)
        day = parse_day(raw_date)
        if day.year != year:
            raise SourceError("TWSE calendar mixed-year response")
        notice = f"{label} {desc}"
        if any(x in notice for x in ("開始交易", "最後交易日", "照常交易", "正常交易", "恢復交易")) and not any(x in label for x in ("不交易", "無交易")):
            continue
        if day.weekday() < 5:
            closed.add(day)  # includes no-trading bank/settlement-only days
    if not closed:
        raise SourceError("TWSE calendar returned no weekday closures")
    return closed

def completed(now: datetime, tz, schedule) -> date:
    local = now.astimezone(tz)
    for delta in range(16):
        day = local.date() - timedelta(days=delta)
        close = schedule(day)
        if close and datetime.combine(day, close, tz) <= local:
            return day
    raise SourceError("Could not derive the last completed cash session")

def number(value: str) -> float:
    try:
        val = Decimal(str(value).strip().replace(",", ""))
    except InvalidOperation as exc:
        raise SourceError("Missing/non-numeric market mark") from exc
    if not val.is_finite() or val <= 0 or val > 10_000_000:
        raise SourceError("Market mark out of range")
    return float(val)

def taiwan_mark(raw: str, wanted: date) -> dict:
    obj = json.loads(raw)
    if str(obj.get("stat", "")).lower() != "ok":
        raise SourceError("TAIEX historical source not OK for exact session")
    fields = obj.get("fields", [])
    names = ("日期", "開盤指數", "最高指數", "最低指數", "收盤指數")
    if not all(key in fields for key in names):
        raise SourceError("TAIEX official OHLC fields changed")
    indexes = [fields.index(key) for key in names]
    rows = [row for row in obj.get("data", []) if parse_day(row[indexes[0]]) == wanted]
    if len(rows) != 1:
        raise SourceError("Exact TAIEX session absent or duplicated")
    values = [number(rows[0][i]) for i in indexes[1:]]
    op, hi, lo, close = values
    if not (lo <= min(op, close) <= max(op, close) <= hi):
        raise SourceError("TAIEX OHLC is internally inconsistent")
    return dict(zip(("open", "high", "low", "close"), values))

def sp500_mark(raw: str, wanted: date) -> float:
    rows = [r for r in csv.DictReader(StringIO(raw))
            if (r.get("observation_date") or r.get("DATE")) == wanted.isoformat()]
    if len(rows) != 1 or "SP500" not in rows[0]:
        raise SourceError("Exact S&P 500 close absent from FRED")
    return number(rows[0]["SP500"])

def collect(now: datetime, get=fetch) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise SourceError("An aware cutoff timestamp is required")
    # The timezone fallback applies only to 2026–28, as does the reviewed
    # calendar. March and November DST transition days are never sessions.
    if NY is None:
        def us_utc_close(day):
            end = nyse_close(day)
            if end is None:
                return None
            first_mar = date(day.year, 3, 1)
            first_nov = date(day.year, 11, 1)
            dst_start = first_mar + timedelta(days=(6-first_mar.weekday()) % 7 + 7)
            dst_end = first_nov + timedelta(days=(6-first_nov.weekday()) % 7)
            return time(end.hour + (4 if dst_start <= day < dst_end else 5))
        us = completed(now, timezone.utc, us_utc_close)
    else:
        us = completed(now, NY, nyse_close)
    tw_cal = {}
    def taiwan_schedule(day: date):
        if day.weekday() >= 5:
            return None
        if day.year not in tw_cal:
            edition = TWSE_CAL.format(year=day.year)
            tw_cal[day.year] = twse_closed(get(edition), day.year)
        return None if day in tw_cal[day.year] else time(13, 30)
    tw = completed(now, TW, taiwan_schedule)
    local = now.astimezone(TW)
    tw_url = TWSE_CLOSE.format(year=tw.year, month=tw.month)
    us_url = FRED_CLOSE.format(day=us.isoformat())
    tw_ohlc = taiwan_mark(get(tw_url), tw)
    us_close = sp500_mark(get(us_url), us)
    prev_us = us - timedelta(days=1)
    while nyse_close(prev_us) is None:
        prev_us -= timedelta(days=1)
    extra, gaps, night = assets(now, get, us, prev_us, tw, taiwan_schedule)
    return {
        "us_trade_date": us.isoformat(),
        "tw_trade_date": tw.isoformat(),
        "night_futures_official_date": night,
        "asset_rows": extra,
        "asset_gaps": gaps,
        "cutoff_source_clock": local.isoformat(),
        "calendars": {"NYSE": NYSE, "TWSE": [TWSE_CAL.format(year=y) for y in sorted(tw_cal)]},
        "observations": {
            "SP500": {"date": us.isoformat(), "close": us_close, "source": us_url,
                      "publisher": "S&P Dow Jones Indices LLC via FRED", "status": "cash_close"},
            "TAIEX": {"date": tw.isoformat(), **tw_ohlc, "source": tw_url,
                      "publisher": "Taiwan Stock Exchange", "status": "cash_ohlc"},
        },
    }

TREASURY = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve&field_tdr_date_value_month={month}"
TAIFEX = "https://www.taifex.com.tw/enl/eng3/futDailyMarketReport?queryDate={day}&commodity_id=TX&marketCode=1"
UST_FIELDS = {"2 Yr": "美國 2 年期公債殖利率", "10 Yr": "美國 10 年期公債殖利率", "30 Yr": "美國 30 年期公債殖利率"}

class Tables(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.rows, self.words, self.row, self.cell = [], [], None, None
        self.feed(html)
        self.close()
    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("th","td") and self.row is not None:
            self.cell = []
    def handle_data(self, data):
        self.words.append(data)
        if self.cell is not None:
            self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ("th","td") and self.cell is not None and self.row is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr":
            if self.row:
                self.rows.append(self.row)
            self.row = None
            self.cell = None

def treasury_row(html, wanted):
    row_lengths = {}
    for row in Tables(html).rows:
        if "Date" in row and all(key in row for key in UST_FIELDS):
            row_lengths[len(row)] = (row.index("Date"), [row.index(k) for k in UST_FIELDS])
        if len(row) not in row_lengths:
            continue
        d, cols = row_lengths[len(row)]
        try:
            parsed = datetime.strptime(row[d], "%m/%d/%Y").date()
        except ValueError:
            continue
        if parsed == wanted:
            return [number(row[i]) for i in cols]
    raise SourceError("Exact Treasury daily par curve absent")

def overnight_row(html, trade_day, physical_day, cutoff):
    doc = Tables(html)
    s = " ".join(" ".join(doc.words).split())
    wanted = trade_day.strftime("%Y/%m/%d")
    physical = physical_day.strftime("%Y/%m/%d")
    if not re.search(r"Date\s*[:：]\s*" + wanted, s) or not re.search(
        r"\bTX\s+" + physical + r"\s+15:00\s*~\s*05:00", s
    ):
        raise SourceError("TAIFEX page does not confirm requested date and after-hours session")
    finish = datetime.combine(physical_day + timedelta(days=1), time(5), TW)
    if finish > cutoff:
        raise SourceError("TAIFEX night session still in progress")
    for row in doc.rows:
        if "Last" in row and "Settlement Price" in row and "Change" in row:
            last_i, change_i, settle_i = [row.index(x) for x in ("Last","Change","Settlement Price")]
            break
    else:
        raise SourceError("TAIFEX expected table columns not found")
    contracts = [r for r in doc.rows if len(r) > settle_i and r[0] == "TX" and re.fullmatch(r"20\d{4}",r[1])]
    if not contracts:
        raise SourceError("TAIFEX TX outright months absent")
    row = min(contracts, key=lambda r: r[1])
    if row[settle_i] not in ("", "-", "—"):
        raise SourceError("TAIFEX night and settlement table scopes conflict")
    change_text = re.sub(r"[▲▼+\s,]", "", row[change_i]).replace("−", "-")
    return {"date":trade_day.isoformat(), "close":number(row[last_i]), "contract":row[1],
            "daily_chg":re.sub(r"[▲▼\s]", "", row[change_i + 1]).replace("−", "-"),
            "change_points":float(change_text) if change_text not in ("", "-") else None,
            "source":TAIFEX.format(day=trade_day.isoformat()), "status":"after_hours_last_not_settlement",
            "session_start":datetime.combine(physical_day,time(15),TW).isoformat(),
            "session_end":finish.isoformat()}

def assets(now, get, us, prev_us, tw, tw_schedule):
    out, gaps, night = {}, {}, None
    try:
        source = TREASURY.format(month=us.strftime("%Y%m"))
        old_source = TREASURY.format(month=prev_us.strftime("%Y%m"))
        current = get(source)
        old = current if old_source == source else get(old_source)
        values = treasury_row(current, us)
        old_values = treasury_row(old, prev_us)
        for key, value, prior in zip(UST_FIELDS.values(), values, old_values):
            out[key] = {"date":us.isoformat(), "close":value, "daily_chg":f"{(value-prior)*100:+.2f} bp",
                        "source":source, "status":"indicative_par_yield", "unit":"%", "change_unit":"bp"}
        a, b = round((values[1]-values[0])*100, 2), round((old_values[1]-old_values[0])*100,2)
        out["美債 2s10s 利差"] = {"date":us.isoformat(), "close":a,"daily_chg":f"{a-b:+.2f} bp",
                                     "source":source, "status":"derived_par_yield_spread", "unit":"bp", "change_unit":"bp"}
    except (ValueError, TypeError, OSError, KeyError):
        gaps["treasury"]="Exact current and previous official par-yield dates not both confirmed"
    try:
        for i in range(1,16):
            wanted = tw + timedelta(days=i)
            if tw_schedule(wanted):
                break
        else:
            raise SourceError("TAIFEX candidate attribution not determined")
        if now.astimezone(TW) < datetime.combine(tw+timedelta(days=1),time(5),TW):
            raise SourceError("TAIFEX night session not yet complete")
        url = TAIFEX.format(day=wanted.isoformat())
        row = overnight_row(get(url),wanted,tw,now)
        out["台指期夜盤（近月）"] = row
        night = row["date"]
    except (ValueError, TypeError, OSError, KeyError):
        gaps["taifex"]="Exact official completed after-hours row not confirmed; no date inferred"
    return out, gaps, night
