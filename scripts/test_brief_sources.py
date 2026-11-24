import json
import unittest
from datetime import date, datetime, timezone

from brief_sources import SourceError, collect, nyse_close, twse_closed

def tw_calendar():
    return json.dumps({"stat":"ok","date":"20260101","fields":["日期","名稱","說明"],
        "data":[["2026-01-01","休市","放假"],["2026-01-02","開始交易日","正常交易"],
                ["2026-02-11","農曆春節前最後交易日","2月12日無交易"],
                ["2026-02-12","市場無交易","僅辦理結算交割"],
                *[[f"2026-02-{d:02}","春節","放假"] for d in range(13,21)]]})

def tw_ohlc(day="115/11/27"):
    return json.dumps({"stat":"OK","fields":["日期","開盤指數","最高指數","最低指數","收盤指數"],
        "data":[[day,"40,000","41,000","39,000","40,100"]]})

class SourceChecks(unittest.TestCase):
    def fixture(self, stale=False, missing_us=False):
        def get(url):
            if "holidaySchedule" in url:
                return tw_calendar()
            if "MI_5MINS" in url:
                return tw_ohlc("115/11/26" if stale else "115/11/27")
            if "fred" in url:
                self.assertIn("cosd=2026-11-25&coed=2026-11-25", url)
                return "observation_date,SP500\n2026-11-25," + ("." if missing_us else "7400.20")
            raise SourceError(url)
        return get

    def test_thanksgiving_carries_us_only(self):
        now=datetime(2026,11,27,13,0,tzinfo=timezone.utc)
        out=collect(now,self.fixture())
        self.assertEqual((out["us_trade_date"],out["tw_trade_date"]), ("2026-11-25","2026-11-27"))
        self.assertEqual(out["observations"]["TAIEX"]["close"],40100)
        self.assertIsNone(out["night_futures_official_date"])

    def test_market_close_and_annual_scope(self):
        self.assertEqual(nyse_close(date(2026,11,27)).hour,13)
        self.assertIsNone(nyse_close(date(2026,11,26)))
        with self.assertRaises(SourceError):
            nyse_close(date(2029,1,3))
        dates=twse_closed(tw_calendar(),2026)
        self.assertIn(date(2026,2,12),dates)
        self.assertNotIn(date(2026,2,11),dates)

    def test_date_or_value_gap_fails(self):
        now=datetime(2026,11,27,13,0,tzinfo=timezone.utc)
        for args in ({"stale":True},{"missing_us":True}):
            with self.assertRaises(SourceError):
                collect(now,self.fixture(**args))

    def test_optional_exact_treasury_and_night(self):
        now=datetime(2026,11,24,0,0,tzinfo=timezone.utc)
        def tab(*rows):
            return '<table>' + ''.join('<tr>' + ''.join(f'<td>{x}</td>' for x in row) + '</tr>' for row in rows) + '</table>'
        def get(url):
            if "holidaySchedule" in url:
                return tw_calendar()
            if "MI_5MINS" in url:
                return tw_ohlc("115/11/23")
            if "fred" in url:
                return "observation_date,SP500\n2026-11-23,7237.17"
            if "treasury" in url:
                return tab(["Date","2 Yr","10 Yr","30 Yr"],["11/20/2026","4.63","4.92","5.31"],
                           ["11/23/2026","4.63","4.92","5.29"])
            if "taifex" in url:
                self.assertIn("queryDate=2026-11-24",url)
                return '<p>Date： 2026/11/24</p><p>TX 2026/11/23 15:00 ~ 05:00</p>' + tab(
                    ["Code","Month","Last","Change","%","Settlement Price"],
                    ["TX","202701","39962","▲3176","▲8.63%","-"],
                    ["TX","202612","39829","▲3170","▲8.65%","-"])
            raise AssertionError(url)
        out=collect(now,get)
        self.assertEqual(out["night_futures_official_date"],"2026-11-24")
        self.assertEqual(out["asset_rows"]["台指期夜盤（近月）"]["close"],39829)
        self.assertEqual(out["asset_rows"]["台指期夜盤（近月）"]["daily_chg"],"8.65%")
        self.assertEqual(out["asset_rows"]["美債 2s10s 利差"]["close"],29)
        self.assertEqual(out["asset_rows"]["美國 30 年期公債殖利率"]["daily_chg"],"-2.00 bp")
        self.assertFalse(out["asset_gaps"])
        def wrong_session(url):
            return get(url).replace("2026/11/23 15:00", "2026/11/22 15:00") if "taifex" in url else get(url)
        out=collect(now,wrong_session)
        self.assertIsNone(out["night_futures_official_date"])
        self.assertIn("taifex",out["asset_gaps"])


if __name__ == "__main__":
    unittest.main()
