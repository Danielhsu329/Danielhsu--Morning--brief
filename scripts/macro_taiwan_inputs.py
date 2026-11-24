"""Independent sources for Taiwan market aggregates and effective Fed Funds."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from brief_sources import Tables, SourceError, parse_day

FMT="https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={day}&response=html"
OTC="https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingIndex?date={day}&response=html"
BFI="https://www.twse.com.tw/rwd/zh/fund/BFI82U?dayDate={day}&response=html&type=day"
EFFR="https://markets.newyorkfed.org/api/rates/unsecured/effr/last/5.json"

def compact(v):
    return re.sub(r"[\s()（）]","",v)

def guard(ok,message):
    if not ok: raise SourceError(message)

def number(value):
    try:
        n=Decimal(str(value).strip().replace(",",""))
    except InvalidOperation as exc:
        raise SourceError("unreadable numeric mark") from exc
    guard(n.is_finite() and abs(n)<10**16,"invalid aggregate")
    return n

def trade_rows(raw,wanted,otc=False):
    doc=Tables(raw)
    h=[["日期","成交張數","金額仟元","筆數","櫃買指數","漲/跌"],
       ["日期","成交股數","成交金額","成交筆數","發行量加權股價指數","漲跌點數"]][not otc]
    headings=[i for i,row in enumerate(doc.rows) if list(map(compact,row))==h]
    guard(len(headings)==1,"expected single exact market table")
    context=compact("".join(doc.words))
    if otc:
        guard("不含上櫃股票鉅額交易" in context,"TPEx block trade scope unclear")
    hits=[]
    for row in doc.rows[headings[0]+1:]:
        if len(row)!=6: continue
        try: day=parse_day(row[0])
        except ValueError: continue
        if day==wanted: hits.append(row)
    guard(len(hits)==1,"no unique exact Taiwan trading date")
    _,volume,amt,trades,idx,ch=hits[0]
    v, a, n, close, change = map(number,(volume,amt,trades,idx,ch))
    guard(min(v,a,n,close)>0 and close-change>0,"invalid market observation")
    return {"volume":int(v),"turnover_twd":round(a*(1000 if otc else 1)), "trades":int(n),
            "close":float(close),"change_points":float(change),"daily_chg":f"{100*change/(close-change):+.2f}%"}

def institutions(raw,wanted):
    doc=Tables(raw)
    label=compact("".join(doc.words))
    ment=f"{wanted.year-1911}年{wanted.month}月{wanted.day}日三大法人買賣金額統計表"
    guard(ment in label,"institutional report date/title mismatch")
    guard(sum(list(map(compact,row))==["單位名稱","買進金額","賣出金額","買賣差額"] for row in doc.rows)==1, "invalid institution headings")
    tags={"外資及陸資不含外資自營商":"twse_foreign_net_twd_bn","自營商避險":"twse_dealer_hedge_twd_bn","合計":"twse_inst_net_twd_bn"}
    result={}
    for row in doc.rows:
        if len(row)!=4 or compact(row[0]) not in tags: continue
        key=tags[compact(row[0])]
        guard(key not in result,"duplicate aggregate row")
        buy,sell,net=map(number,row[1:])
        guard(buy-sell==net,"net institutional amount fails reconciliation")
        result[key]=float(net/10**9)
    guard(len(result)==len(tags),"missing net institutional subgroup")
    return result

def fed_rates(raw,now):
    if now.tzinfo is None: raise SourceError("missing clock timezone")
    try: ny=now.astimezone(ZoneInfo("America/New_York"))
    except ZoneInfoNotFoundError:
        # Offline Windows fixture does not require installed IANA data. Conservative cutoff
        # is at least as restrictive as an Eastern morning publication window.
        from datetime import timezone, timedelta
        ny=now.astimezone(timezone(timedelta(hours=-5)))
    def eligible(d):
        return d<ny.date() if ny.hour>=9 else (ny.date()-d).days>=2
    hits={}
    for r in json.loads(raw)["refRates"]:
        if r.get("type","").upper()!="EFFR":continue
        d=date.fromisoformat(r["effectiveDate"])
        if not eligible(d):continue
        vals=tuple(number(str(r[k])) for k in ("percentRate","targetRateFrom","targetRateTo"))
        if d in hits and hits[d]!=vals: raise SourceError("conflicting effective-date marks")
        hits[d]=vals
    guard(bool(hits),"no cutoff-eligible EFFR")
    d=max(hits); rate,lo,hi=hits[d]
    guard(0 <= lo <= rate <= hi <= 50,"malformed EFFR or target")
    return {"date":d.isoformat(),"source":EFFR,"effective_ffr":float(rate),"target_range":f"{lo:.2f}%–{hi:.2f}%",
            "status":"NY Fed prior effective-date EFFR and corresponding target corridor; not FOMC decision date"}

def extend(e,now,get):
    tw=date.fromisoformat(e["tw_trade_date"]); compact_day=tw.strftime("%Y%m%d")
    assets=e["asset_rows"]; facts={}; e["tw_market_facts"]=facts; gaps={}
    def put(k,val,url,scope,day=tw):
        facts[k]={"value":val,"date":day.isoformat(),"source":url,"scope":scope}
    for otc, url in ((False,FMT.format(day=compact_day)),(True,OTC.format(day=tw.strftime("%Y/%m/%d")))):
        field="tpex" if otc else "twse"
        try:
            row=trade_rows(get(url),tw,otc)
            if not otc:
                guard(abs(row["close"]-e["observations"]["TAIEX"]["close"])<.00001,"listed index sources disagree")
            scope="TPEx excludes block trades; volume lots, amount converted from thousands TWD" if otc else "TWSE total market turnover; not index constituent volume"
            put(field+"_turnover_twd_bn",row["turnover_twd"]/10**9,url,scope)
            if otc:
                assets["台灣櫃買指數 (TPEx)"]={"date":tw.isoformat(),"close":row["close"],
                    "daily_chg":row["daily_chg"],"source":url,"status":scope}
            else:
                e["observations"]["TAIEX"]["daily_chg"]=row["daily_chg"]
        except (SourceError,OSError,KeyError,TypeError,ValueError) as exc:
            gaps[field]=type(exc).__name__
    url=BFI.format(day=compact_day)
    try:
        for k,v in institutions(get(url),tw).items():
            put(k,v,url,"TWSE aggregate recorded cash-market classification, not TPEx or investor intention")
    except (SourceError,OSError,KeyError,TypeError,ValueError) as exc:
        gaps["institutional"]=type(exc).__name__
    if night:=assets.get("台指期夜盤（近月）"):
        put("txf_night_close",night["close"],night["source"],"TAIFEX night last, not settlement",date.fromisoformat(night["date"]))
    try: e["fed_policy_facts"]=fed_rates(get(EFFR),now)
    except (SourceError,OSError,KeyError,TypeError,ValueError) as exc: gaps["effr"]=type(exc).__name__
    e["optional_market_gaps"]=gaps
    return e
