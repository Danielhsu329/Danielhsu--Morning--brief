"""Exercise generated data against the exact latest manually supplied six-tab page."""
from datetime import datetime
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

import generate_brief as g
from verify_public import verify

class TabbedTests(unittest.TestCase):
    def test_fresh_issue_renders_full_six_tabs_without_rewriting_manual_baseline(self):
        source_path=g.ROOT/"archive"/"20261124-1045.html"
        data_before=source_path.read_bytes()
        old_head, old, _=g.template(data_before.decode("utf-8"))
        self.assertEqual(old["meta"]["date"],"2026-11-24")
        self.assertIn("key_events_boundary",old["meta"])
        self.assertNotIn("executive_takeaways",old["meta"])
        fresh_date="2026-11-27"
        def synthetic(v,k=""):
            if isinstance(v,list): return [synthetic(x,k) for x in v]
            if isinstance(v,dict): return {key:synthetic(x,key) for key,x in v.items()}
            if k in {"category","name","ticker","segment","id","rank","probability_pct","signal"} or k.endswith("_pct") and k in {"cash_short_bond_pct","defensive_equity_pct","quality_ai_hardware_pct","commodities_intl_pct"}:
                return v
            if k=="date": return fresh_date
            if k=="close" or k=="daily_chg" or not isinstance(v,str): return None
            return "本地測試資料"
        data=synthetic(old)
        now=datetime(2026,11,27,8,tzinfo=g.TAIPEI)
        e={"us_trade_date":"2026-11-25","tw_trade_date":"2026-11-26","night_futures_official_date":None,
            "observations":{"TAIEX":{"date":"2026-11-26","close":37000.91,"source":"https://www.twse.com.tw/"}},
            "source_exclusions":{"S&P 500":"https://fred.stlouisfed.org/series/SP500"}}
        data["meta"].update({k:e[k] for k in ("us_trade_date","tw_trade_date","night_futures_official_date")})
        data["meta"].update(cutoff_taipei="2026-11-27 08:00 Asia/Taipei",headline_thesis="這是新一期測試主題",
                            key_events_boundary=["測試：美台現貨日期分列，未取得欄位留空。"])
        for row in data["cross_assets_and_macro"]["assets"]:
            if "TAIEX" in row["name"]: row["close"]=37000.91
        data["taiwan_market_and_bottom_checklist"]["spot_and_futures"]["total_txf_oi_note"]=None if "total_txf_oi_note" in old["taiwan_market_and_bottom_checklist"]["spot_and_futures"] else None
        if "total_txf_oi_note" not in old["taiwan_market_and_bottom_checklist"]["spot_and_futures"]:
            del data["taiwan_market_and_bottom_checklist"]["spot_and_futures"]["total_txf_oi_note"]
        # Cash figure strings are not permitted; keep descriptive fields but clear numeric ones.
        for company in data["us_cashflow_penetration"]["companies"]:
            for k in company.keys()-{"ticker","period","alert"}: company[k]=None
        for k in data["taiwan_market_and_bottom_checklist"]["spot_and_futures"]:
            if k!="note": data["taiwan_market_and_bottom_checklist"]["spot_and_futures"][k]=None
        for company in data["ai_supply_chain"]["core_companies"]:
            company["oct_rev_yoy"]=None
        twsc=data["ai_supply_chain"]["core_companies"][0]
        self.assertEqual(twsc["ticker"],"2330.TW")
        e["tw_monthly_revenue"]={twsc["ticker"]:{"revenue_twd_bn":586.89,"period":"2026-10",
             "yoy_display":"+59.7%","table_date":"2026-11-17","source":"https://pr.tsmc.com/english/news/3349"}}
        twsc.update(oct_rev_twd_bn=586.89,oct_rev_yoy="+59.7%")
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            shutil.copy(source_path,root/"index.html")
            shutil.copytree(g.ROOT/"archive",root/"archive")
            archives_before={p.name:p.read_bytes() for p in (root/"archive").iterdir()}
            checked=g.bind(data,old,e,now)
            out=g.staging_contents(root,checked)
            self.assertEqual(data_before,source_path.read_bytes())
            self.assertEqual((root/"index.html").read_bytes(),data_before)
            self.assertEqual(archives_before,{p.name:p.read_bytes() for p in (root/"archive").iterdir()})
            home, archive=out["index.html"],out["archive/20261127.html"]
            for page in (home,archive):
                self.assertEqual(g.template(page)[1],checked)
                self.assertIn("這是新一期測試主題",page)
                self.assertNotIn(old["meta"]["headline_thesis"],page)
                for prior in ("2026-11-24 10:45","2026-11-24 07:21","$500/噸","機構現金 3.6%","歸屬 11/24"):
                    self.assertNotIn(prior,page)
                for tab in ("macro","uscf","tw","aisc","energy","scen"):
                    self.assertIn(f'id="tab-{tab}"',page)
                self.assertIn("十億美元",page)
                self.assertIn("briefHtml(m.note)",page)
                self.assertIn("dataBoundaryText",page)
                self.assertIn("${briefHtml(item)}",page)
                self.assertIn("assetCountLabel",page)
                self.assertIn("586.89",page)
                self.assertIn("月營收 2026-10",page)
                self.assertIn("fmtNum(c.oct_rev_twd_bn, '', '十億元')",page)
                self.assertNotIn("10 月營收 (YoY)",page)
            for historic in ("20261124.html","20261124-1045.html","20261124-1136.html"):
                self.assertIn(historic,archives_before)
                self.assertIn(historic,out["archive/index.html"])
            self.assertIn('href="./archive/"',home)
            self.assertNotIn('href="./archive/"',archive)
            self.assertIn('href="./"',archive)
            self.assertIn('href="../"',archive)
            mapping={k:v.encode("utf-8") for k,v in out.items()}
            mapping[""]=mapping["index.html"]
            mapping["archive/"]=mapping["archive/index.html"]
            verify(mapping.__getitem__,fresh_date,hashlib.sha256(mapping["data/latest.json"]).hexdigest())
            # A subsequent issue must not duplicate the render hardening or nav.
            (root/"index.html").write_text(home,encoding="utf-8")
            checked["meta"].update(date="2026-11-28",cutoff_taipei="2026-11-28 08:00 Asia/Taipei")
            future=g.staging_contents(root,checked)["index.html"]
            self.assertEqual(future.count("function briefHtml("),1)
            self.assertEqual(future.count('href="./archive/"'),1)

    def test_1136_static_render_has_one_payload_and_both_correct_units(self):
        home=g.ROOT/"index.html"
        archive=g.ROOT/"archive"/"20261124-1136.html"
        before=(home.read_bytes(),archive.read_bytes())
        self.assertIn(b"./data/manifest.json",before[0])
        _, example, _=g.template(home.read_text(encoding="utf8"))
        record={**example,"meta":{**example["meta"],"date":"2026-11-27",
                "cutoff_taipei":"2026-11-27 08:00 Asia/Taipei",
                "us_trade_date":"2026-11-25","tw_trade_date":"2026-11-26","night_futures_official_date":None,
                "headline_thesis":"Offline fixture", "key_events_boundary":["Fixture event"]}}
        with tempfile.TemporaryDirectory() as temp:
            location=Path(temp)
            shutil.copy(home,location/"index.html")
            shutil.copytree(g.ROOT/"archive",location/"archive")
            out=g.staging_contents(location,record)
            for key in ("index.html","archive/20261127.html"):
                page=out[key]
                self.assertEqual(g.template(page)[1],record)
                self.assertNotIn("fetchJsonNoCache",page)
                self.assertNotIn("2026-11-24 11:36",page)
                self.assertIn('val: sf.twse_turnover_twd_bn, unit: " 十億元"',page)
                self.assertIn('formatNullable(c.oct_rev_twd_bn, " 十億元")',page)
                self.assertIn('briefHtml(item)',page)
                self.assertIn("eventBoundaryList",page)
                self.assertIn("assetCountBadge",page)
            self.assertIn('href="./archive/"',out["index.html"])
            self.assertIn('href="../"',out["archive/20261127.html"])
            mapping={k:v.encode("utf-8") for k,v in out.items()}
            mapping[""]=mapping["index.html"]
            mapping["archive/"]=mapping["archive/index.html"]
            verify(mapping.__getitem__,"2026-11-27",hashlib.sha256(mapping["data/latest.json"]).hexdigest())
            (location/"index.html").write_text(out["index.html"],encoding="utf8")
            record["meta"].update(date="2026-11-28",cutoff_taipei="2026-11-28 08:00 Asia/Taipei")
            second=g.staging_contents(location,record)["index.html"]
            self.assertEqual(second.count("function briefHtml("),1)
            self.assertNotIn("fetchJsonNoCache",second)

            for issue in ("20261124.html","20261124-1045.html","20261124-1136.html"):
                self.assertIn(issue,out["archive/index.html"])
        self.assertEqual(before,(home.read_bytes(),archive.read_bytes()))
