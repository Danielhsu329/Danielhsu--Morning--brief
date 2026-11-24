"""Pure EDGAR accession-based quarterly cash-flow extraction and read-only collection."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import math
import re
from time import sleep
from urllib.request import Request, urlopen

CIKS = {"MSFT":789019,"GOOGL":1652044,"META":1326801,"AMZN":1018724,"NVDA":1045810,"PG":80424,"WMT":104169}
FORMS = {"10-K","10-K/A","10-Q","10-Q/A"}
CFO = "NetCashProvidedByUsedInOperatingActivities"
CAPEX = "PaymentsToAcquirePropertyPlantAndEquipment"
SBC = "ShareBasedCompensation"
DA = "DepreciationDepletionAndAmortization"
NI = "NetIncomeLoss"
REVENUES = ("RevenueFromContractWithCustomerExcludingAssessedTax","Revenues","SalesRevenueNet")
HOST = "https://data.sec.gov/"
MAX_BYTES = 24_000_000
BILLION = 10**9

class SECSourceError(ValueError):
    """The selected date, accession, or matching XBRL contexts are absent."""

@dataclass(frozen=True)
class Filing:
    period: date
    accepted: datetime
    accession: str
    form: str
    document: str

def filing_index(raw, cutoff, ticker):
    ci = CIKS[ticker]
    recent = raw["filings"]["recent"]
    if int(raw["cik"]) != ci:
        raise SECSourceError("cik mismatch")
    filings = {}
    for form, period, accepted, acc, doc in zip(*(recent[k] for k in
                              ("form","reportDate","acceptanceDateTime","accessionNumber","primaryDocument"))):
        if form not in FORMS or not period or not accepted or not re.fullmatch(r"\d{10}-\d{2}-\d{6}",acc):
            continue
        time = datetime.fromisoformat(accepted.replace("Z","+00:00"))
        if time.utcoffset() is None or time > cutoff:
            continue
        end = date.fromisoformat(period)
        # Do not silently choose a prior quarter when latest accession is unavailable.
        filings[acc]=Filing(end,time,acc,form,doc)
    if not filings:
        raise SECSourceError("no quarterly or annual filing at cutoff")
    latest=max(filings.values(), key=lambda f:(f.period,f.accepted))
    return latest, filings

def observe(raw, tag, base, filings, allowed_end, newest):
    us = raw["facts"].get("us-gaap",{})
    data = us.get(tag,{}).get("units",{}).get("USD",[])
    rows = []
    for r in data:
        if r.get("end") != allowed_end.isoformat() or not r.get("start") or r.get("accn") not in filings:
            continue
        filing = filings[r["accn"]]
        if (newest and filing.accession != base.accession) or filing.accepted > base.accepted:
            continue
        v = r.get("val")
        if type(v) not in (int,float) or not math.isfinite(v):
            continue
        rows.append((date.fromisoformat(r["start"]),v,filing))
    return rows

def choose(records):
    ranked = sorted(records,key=lambda a:a[2].accepted,reverse=True)
    first = ranked[0]
    if len({(r[0],r[1]) for r in ranked if r[2].accession == first[2].accession}) != 1:
        raise SECSourceError("ambiguous values in same filed context")
    return first

def quarter(raw, tag, base, filings, allow_subtraction=True):
    current = observe(raw,tag,base,filings,base.period,True)
    # SEC frames are intentionally not used; fiscal calendars differ.
    direct = [r for r in current if 76 <= (base.period-r[0]).days + 1 <= 110]
    def evidence(r,end):
        return {"tag":tag,"unit":"USD","start":r[0].isoformat(),"end":end.isoformat(),
                "accession":r[2].accession,"filing_accepted":r[2].accepted.isoformat(),"value":r[1]}
    if direct:
        selected=choose(direct)
        return {"value":selected[1],"method":"reported_quarter","quarter_start":selected[0].isoformat(),
                "evidence":[evidence(selected,base.period)]}
    if not allow_subtraction:
        raise SECSourceError("direct quarter not filed")
    candidates=[]
    for end in sorted({f.period for f in filings.values()},reverse=True):
        if not 76 <= (base.period-end).days <= 110:
            continue
        for r in current:
            current_days=(base.period-r[0]).days+1
            if not 150 <= current_days <= 380:
                continue
            priors=observe(raw,tag,base,filings,end,False)
            same_ytd=[p for p in priors if p[0] == r[0] and 76 <= (end-p[0]).days+1 <= 300]
            if same_ytd:
                candidates.append((end,r,choose(same_ytd)))
    if len(candidates)!=1:
        raise SECSourceError("aligned quarter YTD pair unavailable or ambiguous")
    end,later,prior=candidates[0]
    return {"value":later[1]-prior[1],"method":"current_ytd_minus_prior_ytd",
            "quarter_start":(end+timedelta(days=1)).isoformat(),
            "evidence":[evidence(later,base.period),evidence(prior,end)]}

def compute(company, submissions, facts, cutoff):
    cik=CIKS[company]
    if int(facts["cik"]) != cik:
        raise SECSourceError("companyfacts cik mismatch")
    base, filings=filing_index(submissions,cutoff,company)
    outcome={}
    for field, tags in (("cfo_bn",(CFO,)),("capex_bn",(CAPEX,)),("sbc_bn",(SBC,)),
                        ("revenue_bn",REVENUES),("net_income_bn",(NI,)),("da_bn",(DA,))):
        for tag in tags:
            try: outcome[field]=quarter(facts,tag,base,filings);break
            except SECSourceError: continue
    required={"cfo_bn","capex_bn"}
    if not required <= outcome.keys():
        raise SECSourceError("quarter cash flow or cash PP&E payments unavailable")
    start = outcome["cfo_bn"]["quarter_start"]
    if outcome["capex_bn"]["quarter_start"] != start:
        raise SECSourceError("quarter cash flow and PP&E periods differ")
    outcome = {k:v for k,v in outcome.items() if v["quarter_start"] == start}
    actual = {k:v["value"]/BILLION for k,v in outcome.items()}
    if actual["capex_bn"]<0:
        raise SECSourceError("unexpected sign for cash PP&E payments")
    fcf=(outcome["cfo_bn"]["value"]-outcome["capex_bn"]["value"])/BILLION
    actual["fcf_bn"]=fcf
    actual["fcf_to_cfo_pct"]=(fcf/actual["cfo_bn"]*100) if actual["cfo_bn"]>0 else None
    actual["fcf_ex_sbc_bn"]=(outcome["cfo_bn"]["value"]-outcome["capex_bn"]["value"]-outcome["sbc_bn"]["value"])/BILLION if "sbc_bn" in outcome else None
    if not re.fullmatch(r"[\w.-]+",base.document):
        raise SECSourceError("invalid filed document path")
    return {"ticker":company,"period_start":start,"period_end":base.period.isoformat(),
            "source":f"https://www.sec.gov/Archives/edgar/data/{cik}/{base.accession.replace('-','')}/{base.document}",
            "accession":base.accession,"accepted_at":base.accepted.isoformat(),
            "values":actual,"source_values":outcome,
            "derived":{"fcf_bn":"CFO minus cash payments to acquire PP&E; not issuer-adjusted FCF",
                       "fcf_to_cfo_pct":"derived FCF divided by positive CFO",
                       "fcf_ex_sbc_bn":"derived FCF less stock-based compensation; not a separate realized cash flow"}}

def get_json(url, contact):
    req=Request(url,headers={"User-Agent":f"MorningBrief Research {contact}","Accept":"application/json"})
    with urlopen(req,timeout=11) as response:
        if not response.geturl().startswith(HOST):
            raise SECSourceError("unexpected EDGAR redirect")
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES: raise SECSourceError("EDGAR response exceeds size bound")
    return json.loads(raw)

def collect(cutoff, contact, fetch=get_json, wait=sleep):
    """Return source-backed results and coarse blockers, not incomplete fake rows."""
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise SECSourceError("timezone-aware cutoff required")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",contact or ""):
        raise SECSourceError("explicit project SEC contact is required")
    results, gaps = {}, {}
    for ticker, cik in CIKS.items():
        try:
            index=fetch(f"{HOST}submissions/CIK{cik:010}.json",contact)
            wait(.2)
            facts=fetch(f"{HOST}api/xbrl/companyfacts/CIK{cik:010}.json",contact)
            results[ticker]=compute(ticker,index,facts,cutoff)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            gaps[ticker]=type(exc).__name__
        finally:
            wait(.2)
    return results,gaps
