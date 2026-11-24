"""Offline fixture using the actual 6-module entry point and a copied public template."""
import copy
from datetime import datetime
from pathlib import Path
import tempfile
import shutil
import unittest

import generate_brief as g

class BriefTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        shutil.copy(g.ROOT/"index.html",self.root/"index.html")
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

if __name__=="__main__": unittest.main()
