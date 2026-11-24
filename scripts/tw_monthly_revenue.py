"""Exchange-reported monthly revenue only; never quarterly coverage."""
from datetime import date
from decimal import Decimal
import json
from brief_sources import SourceError

FEEDS = (
    ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O", ("3131","3324")),
    ("https://openapi.twse.com.tw/v1/opendata/t187ap05_L", ("2330","3583","3017")),
)
TICKER="公司代號"
PERIOD="資料年月"
ISSUED="出表日期"
REV="營業收入-當月營收"
PRIOR="營業收入-去年當月營收"
YOY="營業收入-去年同月增減(%)"

def parse(raw, codes, now, source):
    rows=json.loads(raw)
    if not isinstance(rows,list):
        raise SourceError("monthly revenue feed not an array")
    observed={}
    report_month=now.date().replace(day=1)
    for code in codes:
        eligible={}
        ambiguous=set()
        for r in rows:
            if not isinstance(r,dict) or r.get(TICKER)!=code: continue
            try:
                period, issued = r[PERIOD], r[ISSUED]
                if len(period)!=5 or len(issued)!=7 or not (period.isascii() and period.isdigit() and issued.isascii() and issued.isdigit()):
                    continue
                start=date(1911+int(period[:3]),int(period[3:]),1)
                filed=date(1911+int(issued[:3]),int(issued[3:5]),int(issued[5:]))
                # Hourless exchange snapshots on the report day are not as-of evidence.
                filing_month=filed.replace(day=1)
                if not (start < report_month and start < filing_month and filed < now.date()): continue
                if start in eligible: ambiguous.add(start)
                eligible[start]=(r,filed)
            except (ArithmeticError,TypeError,ValueError,KeyError):
                continue
        if not eligible: continue
        start=max(eligible)
        if start in ambiguous: continue
        r,filed=eligible[start]
        try:
            revenue, prior = (int(str(r[k]).replace(",","")) for k in (REV,PRIOR))
            yoy=Decimal(str(r[YOY]))
            if min(revenue,prior)<=0 or not yoy.is_finite(): continue
            if abs(yoy-100*(Decimal(revenue)/prior-1))>Decimal("0.055"): continue
        except (ArithmeticError,TypeError,ValueError,KeyError):
            continue
        observed[code+".TW"]={"period":start.strftime("%Y-%m"),"table_date":filed.isoformat(),
             "revenue_twd_thousand":revenue,"prior_year_twd_thousand":prior,
             "revenue_twd_bn":revenue/10**6,"yoy_reported_pct":str(yoy),"yoy_display":f"{yoy:+.1f}%",
             "source":source,"scope":"exchange monthly consolidated revenue; not quarterly financials"}
    return observed

def collect(now,get):
    if now.tzinfo is None: raise SourceError("missing report cutoff timezone")
    result={}
    for source,codes in FEEDS:
        try: result.update(parse(get(source),codes,now,source))
        except (OSError,ValueError,TypeError,KeyError):
            continue
    gaps={code+".TW":"No complete unambiguous pre-cutoff month in currently supplied official snapshot" for _,codes in FEEDS
          for code in codes if code+".TW" not in result}
    return result,gaps
