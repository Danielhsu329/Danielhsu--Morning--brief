"""Offline fixture using the actual 6-module entry point and a copied public template."""
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import shutil
import unittest

import generate_brief as g
from verify_public import verify

class BriefTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        # Keep November 23 as an independent historical fixture after the manual homepage changes.
        shutil.copy(g.ROOT/"archive"/"20261123.html",self.root/"index.html")
        shutil.copytree(g.ROOT/"archive",self.root/"archive")
        self.src=(self.root/"index.html").read_text(encoding="utf-8")
        _,self.ex,_=g.template(self.src)
        self.now=datetime(2026,11,27,8,tzinfo=g.TAIPEI)
        self.e={"us_trade_date":"2026-11-25","tw_trade_date":"2026-11-26","night_futures_official_date":None,
                "observations":{"SP500":{"date":"2026-11-25","close":7200.41,"source":"https://fred.stlouisfed.org/series/SP500"},
                                "TAIEX":{"date":"2026-11-26","close":37000.93,"source":"https://www.twse.com.tw/"}}}
        self.data=copy.deepcopy(self.ex)
        self.data['meta'].update({k:self.e[k] for k in ("us_trade_date","tw_trade_date","night_futures_official_date")})
        self.data['meta'].update(date="2026-11-27",cutoff_taipei="2026-11-27 08:00 Asia/Taipei")
        def sanitize(x):
            if isinstance(x,dict):
                for k,v in x.items():
                    if isinstance(v,str) and g.SCRIPT_TEXT.search(v): x[k]=v.replace("<","＜").replace(">","＞")
                    else: sanitize(v)
            elif isinstance(x,list):
                for v in x: sanitize(v)
        sanitize(self.data)
        cross=self.data["cross_assets_and_macro"]
        module=self.data["commodities_sentiment_and_scenarios"]
        for obj in (self.data["taiwan_market_and_bottom_checklist"]["spot_and_futures"], cross["fed_policy"], *cross["macro_indicators"],
                    *self.data["us_cashflow_penetration"]["companies"], *self.data["ai_supply_chain"]["core_companies"],
                    module["energy_power_and_sentiment"]):
            for k,v in obj.items():
                if type(v) in (int,float): obj[k]=None
        for company in self.data["ai_supply_chain"]["core_companies"]:
            company["oct_rev_yoy"]=None
        for row in cross["assets"]:
            row["close"]=None
            row["daily_chg"]=None
            for sym,name in g.CORE.items():
                if row["name"]==name: row["close"]=self.e["observations"][sym]["close"]
    def test_valid_renders_same_layout_archive_and_never_writes(self):
        validated=g.bind(self.data,self.ex,self.e,self.now)
        outputs=g.staging_contents(self.root,validated)
        self.assertIn("美股現貨 2026-11-25｜台股現貨 2026-11-26",outputs["index.html"])
        self.assertIn('id="navBriefDate"',outputs["archive/20261127.html"])
        self.assertIn('href="../"',outputs["archive/20261127.html"])
        self.assertEqual(set(outputs),{'index.html','archive/index.html','archive/20261127.html','data/2026-11-27.json','data/latest.json','data/manifest.json'})
        _, loaded, _ = g.template(outputs["index.html"])
        self.assertEqual(loaded,validated)
        self.assertEqual(self.src,(self.root/"index.html").read_text(encoding="utf-8"))
        self.assertFalse((self.root/"archive"/"20261127.html").exists())
    def test_wrong_exact_close_or_stale_label_do_not_touch_good_issue(self):
        self.data['cross_assets_and_macro']['assets'][0]['close']=7200.42
        with self.assertRaisesRegex(ValueError,"differs"):
            g.bind(self.data,self.ex,self.e,self.now)
        self.data['cross_assets_and_macro']['assets'][0]['close']=7200.41
        self.data['meta']['tw_trade_date']="2026-11-25"
        with self.assertRaisesRegex(ValueError,"metadata"):
            g.bind(self.data,self.ex,self.e,self.now)
        self.assertEqual(self.src,(self.root/"index.html").read_text(encoding="utf-8"))
    def test_unverified_wti_or_script_text_refuses(self):
        row=next(x for x in self.data['cross_assets_and_macro']['assets'] if x['name']=="WTI 原油")
        row["close"]=79.99
        with self.assertRaisesRegex(ValueError,"must be null"):
            g.bind(self.data,self.ex,self.e,self.now)
        row["close"]=None
        self.data["meta"]["headline_thesis"]="</script><img src=x>"
        with self.assertRaisesRegex(ValueError,"unsafe"):
            g.bind(self.data,self.ex,self.e,self.now)
    def test_duplicate_invalid_json_and_same_day_archive_refused(self):
        with self.assertRaises(ValueError): g.read_json('{"x":1,"x":2}')
        with self.assertRaises(ValueError): g.read_json('{"x":NaN}')
        (self.root/"archive"/"20261127.html").write_text("known good",encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"immutable"):
            g.staging_contents(self.root,self.data)

    def test_public_readback_asserts_same_bytes_and_exact_payload(self):
        result=g.staging_contents(self.root,g.bind(self.data,self.ex,self.e,self.now))
        pages={k:v.encode("utf-8") for k,v in result.items()}
        pages[""]=pages["index.html"]
        pages["archive/"]=pages["archive/index.html"]
        digest=hashlib.sha256(pages["data/latest.json"]).hexdigest()
        verify(pages.__getitem__,"2026-11-27",digest)
        for path in ("archive/20261127.html","data/2026-11-27.json","data/manifest.json"):
            baseline=pages[path]
            pages[path]=baseline.replace(b"2026-11-27",b"2026-11-26",1) if not path.endswith(".html") else baseline.replace(b"7200.41",b"7200.42",1)
            with self.assertRaises(ValueError):
                verify(pages.__getitem__,"2026-11-27",digest)
            pages[path]=baseline

    def test_unlicensed_spx_omitted_and_sparse_production_blocked(self):
        self.e["source_exclusions"]={"S&P 500":"https://fred.stlouisfed.org/series/SP500"}
        self.e["observations"].pop("SP500")
        spx=self.data["cross_assets_and_macro"]["assets"][0]
        with self.assertRaisesRegex(ValueError,"redistribution"):
            g.bind(self.data,self.ex,self.e,self.now)
        spx["close"]=None
        self.assertIsNone(g.bind(self.data,self.ex,self.e,self.now)["cross_assets_and_macro"]["assets"][0]["close"])
        self.assertIn("fred.stlouisfed.org/series/SP500",spx["note"])
        with self.assertRaisesRegex(ValueError,"coverage"):
            g.check_production_coverage(self.ex,self.e)

    def test_display_rejects_ytd_company_value(self):
        row=next(c for c in self.data["us_cashflow_penetration"]["companies"] if c["ticker"]=="WMT")
        row.update(period="2026-10-31",cfo_bn=29.4,capex_bn=8.0,fcf_bn=2.0)
        self.e["us_company_financials"]={"WMT":{"period_end":"2026-10-31",
            "source":"https://www.sec.gov/Archives/edgar/data/104169/fixture.htm",
            "values":{"cfo_bn":10., "capex_bn":8., "fcf_bn":2.}}}
        with self.assertRaisesRegex(ValueError,"WMT.*cfo_bn"):
            g.bind(self.data,self.ex,self.e,self.now)
        row["cfo_bn"]=10.
        updated=g.bind(self.data,self.ex,self.e,self.now)
        self.assertIn("sec.gov",updated["us_cashflow_penetration"]["companies"][-1]["alert"])

    def test_taiwan_and_fed_cannot_be_relabelled_or_fabricated(self):
        self.e["fed_policy_facts"]={"target_range":"3.75%–4.00%","effective_ffr":3.88,
            "date":"2026-11-20","source":"https://markets.newyorkfed.org/"}
        self.e["tw_market_facts"]={"twse_inst_net_twd_bn":{"value":-52.103950743,"date":"2026-11-26",
            "source":"https://www.twse.com.tw/","scope":"listed aggregate only"}}
        fed=self.data["cross_assets_and_macro"]["fed_policy"]
        spot=self.data["taiwan_market_and_bottom_checklist"]["spot_and_futures"]
        fed.update(current_rate_range="3.75%–4.00%",effective_ffr=3.88)
        spot["twse_inst_net_twd_bn"]=-52
        with self.assertRaisesRegex(ValueError,"incorrect supplied Taiwan"):
            g.bind(self.data,self.ex,self.e,self.now)
        spot["twse_inst_net_twd_bn"]=-52.103950743
        fed["effective_ffr"]=3.9
        with self.assertRaisesRegex(ValueError,"Fed rate"):
            g.bind(self.data,self.ex,self.e,self.now)
        fed["effective_ffr"]=3.88
        out=g.bind(self.data,self.ex,self.e,self.now)
        self.assertIn("2026-11-20",out["cross_assets_and_macro"]["fed_policy"]["current_rate_range"])
        self.assertIn("listed aggregate only",spot["margin_balance_note"])
        self.assertIsNone(spot["tpex_foreign_net_twd_bn"])

    def test_unsupported_manual_tab_layout_refused_without_modifying_it(self):
        incompatible=self.src.replace('id="badgeSpot"','id="manual-tab-spot"')
        page=self.root/"index.html"
        page.write_text(incompatible,encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"not compatible"):
            g.staging_contents(self.root,self.data)
        self.assertEqual(page.read_text(encoding="utf-8"),incompatible)

if __name__=="__main__": unittest.main()
