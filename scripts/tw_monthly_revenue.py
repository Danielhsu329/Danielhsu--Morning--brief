"""Exchange-reported monthly revenue only; never quarterly coverage."""
from datetime import date, timedelta
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
    previous_month=(now.date().replace(day=1)-timedelta(days=1)).replace(day=1)
    for code in codes:
        matched=[r for r in rows if isinstance(r,dict) and r.get(TICKER)==code]
        if len(matched)!=1: continue
        r=matched[0]
        try:
            period, issued = r[PERIOD], r[ISSUED]
            if len(period)!=5 or len(issued)!=7 or not (period.isascii() and period.isdigit() and issued.isascii() and issued.isdigit()):
                continue
            start=date(1911+int(period[:3]),int(period[3:]),1)
            filed=date(1911+int(issued[:3]),int(issued[3:5]),int(issued[5:]))
            # 出表日期 has no time. Do not use issue-day snapshots for an earlier morning cutoff.
            if start!=previous_month or not start < filed < now.date(): continue
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
    gaps={code+".TW":"Exact prior month and pre-cutoff exchange row unavailable" for _,codes in FEEDS
          for code in codes if code+".TW" not in result}
    return result,gaps
