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
        source_path=g.ROOT/"index.html"
        data_before=source_path.read_bytes()
        old_head, old, _=g.template(data_before.decode("utf-8"))
        self.assertEqual(old["meta"]["date"],"2026-11-24")
        self.assertIn('href="./archive/"',old_head)
        self.assertIn("data_boundary_note",old["meta"])
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
                            data_boundary_note="測試：美台現貨日期分列，未取得欄位留空。")
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
                for prior in ("2026-11-24 07:21","$500/噸","機構現金 3.6%","歸屬 11/24"):
                    self.assertNotIn(prior,page)
                for tab in ("macro","uscf","tw","aisc","energy","scen"):
                    self.assertIn(f'id="tab-{tab}"',page)
                self.assertIn("十億美元",page)
                self.assertIn("briefHtml(m.note)",page)
                self.assertIn("dataBoundaryText",page)
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
