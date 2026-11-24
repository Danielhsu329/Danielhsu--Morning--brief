import copy
from datetime import datetime, timezone
import unittest
import sec_company_cashflow as sec

Q1="0000789019-26-000001"
Q2="0000789019-26-000002"
Q3="0000789019-26-000003"
AFTER="0000789019-26-000004"
CUTOFF=datetime(2026,11,24,0,0,tzinfo=timezone.utc)

def fixture():
    recent={"form":["10-Q","10-Q","10-Q","10-Q/A"],
            "reportDate":["2026-03-31","2026-06-30","2026-09-30","2026-09-30"],
            "acceptanceDateTime":["2026-05-01T19:15:00Z","2026-08-01T19:15:00Z",
                                  "2026-11-01T19:15:00Z","2026-11-24T00:00:01Z"],
            "accessionNumber":[Q1,Q2,Q3,AFTER],"primaryDocument":["msft-q1.htm","msft-q2.htm","msft-q3.htm","msft-amend.htm"]}
    data={"cik":789019,"filings":{"recent":recent}}
    def tag(q1,q2,q3):
        return {"units":{"USD":[
            {"start":"2026-01-01","end":"2026-03-31","val":q1*sec.BILLION,"accn":Q1},
            {"start":"2026-01-01","end":"2026-06-30","val":q2*sec.BILLION,"accn":Q2},
            {"start":"2026-01-01","end":"2026-09-30","val":q3*sec.BILLION,"accn":Q3},
            {"start":"2026-01-01","end":"2026-09-30","val":999*sec.BILLION,"accn":AFTER}]}}
    facts={"cik":789019,"facts":{"us-gaap":{sec.CFO:tag(20,49,91),sec.CAPEX:tag(9,25,60),sec.SBC:tag(2,7,13)}}}
    return data,facts

class QuarterTests(unittest.TestCase):
    def test_ytd_subtraction_no_double_count_no_lookahead(self):
        index,facts=fixture()
        out=sec.compute("MSFT",index,facts,CUTOFF)
        self.assertEqual(out["accession"],Q3)
        for field,value in {"cfo_bn":42,"capex_bn":35,"fcf_bn":7,"fcf_ex_sbc_bn":1}.items():
            self.assertEqual(out["values"][field],value)
        self.assertEqual(out["source_values"]["cfo_bn"]["method"],"current_ytd_minus_prior_ytd")
        self.assertEqual([x["accession"] for x in out["source_values"]["cfo_bn"]["evidence"]],[Q3,Q2])
    def test_exact_direct_preferred_and_missing_sbc_not_zero(self):
        index,facts=fixture()
        values=facts["facts"]["us-gaap"]
        values[sec.CFO]["units"]["USD"].append({"start":"2026-07-01","end":"2026-09-30","val":43*sec.BILLION,"accn":Q3})
        del values[sec.SBC]
        out=sec.compute("MSFT",index,facts,CUTOFF)
        self.assertEqual(out["values"]["cfo_bn"],43)
        self.assertEqual(out["source_values"]["cfo_bn"]["method"],"reported_quarter")
        self.assertIsNone(out["values"]["fcf_ex_sbc_bn"])
    def test_different_fiscal_starts_and_bad_values_fail(self):
        index,facts=fixture()
        facts["facts"]["us-gaap"][sec.CAPEX]["units"]["USD"][1]["start"]="2026-02-01"
        with self.assertRaisesRegex(sec.SECSourceError,"PP&E"):
            sec.compute("MSFT",index,facts,CUTOFF)
    def test_no_silent_fallback_when_latest_filing_has_no_facts(self):
        index,facts=fixture()
        all_facts=facts["facts"]["us-gaap"]
        for val in all_facts.values():
            val["units"]["USD"]=[r for r in val["units"]["USD"] if r["accn"] in (Q1,Q2)]
        with self.assertRaises(sec.SECSourceError):
            sec.compute("MSFT",index,facts,CUTOFF)
    def test_all_seven_are_called_with_bound_same_hosts_and_safe_results(self):
        index,facts=fixture()
        visited=[]
        def feed(url,contact):
            self.assertTrue(url.startswith(sec.HOST))
            visited.append(url)
            ci=int(url.split("CIK")[-1].split(".")[0])
            obj=copy.deepcopy(index if "submissions" in url else facts)
            obj["cik"]=ci
            return obj
        result,gaps=sec.collect(CUTOFF,"operator@example.org",fetch=feed,wait=lambda _:None)
        self.assertEqual(set(result),set(sec.CIKS))
        self.assertEqual(gaps,{})
        self.assertEqual(len(visited),14)
