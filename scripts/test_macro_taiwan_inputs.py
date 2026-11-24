import json
from datetime import date, datetime, timezone
import unittest
import macro_taiwan_inputs as m

D=date(2026,11,23)
NOW=datetime(2026,11,24,0,tzinfo=timezone.utc)
def table(headers,rows,caption=""):
    def r(tag, cells): return "<tr>"+''.join(f"<{tag}>{x}</{tag}>" for x in cells)+"</tr>"
    return "<table><caption>"+caption+"</caption>"+r("th",headers)+''.join(r("td",row) for row in rows)+"</table>"
FMT=table(["日期","成交股數","成交金額","成交筆數","發行量加權股價指數","漲跌點數"],
          [["115/11/23","15,947,613,387","1,113,743,193,221","5,400,204","36,811.89","778.60"]])
OTC=table(["日 期","成交張數","金額（仟元）","筆數","櫃買指數","漲/跌"],
          [["115/11/23","928,486","162,025,173","802,626","270.90","7.59"]],"以上資料不含上櫃股票鉅額交易")
BFI=table(["單位名稱","買進金額","賣出金額","買賣差額"],[
        ["自營商(避險)","47,007,433,056","63,109,307,602","-16,101,874,546"],
        ["外資及陸資(不含外資自營商)","484,813,745,109","513,761,625,104","-28,947,879,995"],
        ["合計","570,413,771,708","622,517,722,451","-52,103,950,743"]],"115年11月23日 三大法人買賣金額統計表")
EFFR=json.dumps({"refRates":[{"type":"EFFR","effectiveDate":"2026-11-23","percentRate":3.9,"targetRateFrom":3.75,"targetRateTo":4.0},
                      {"type":"EFFR","effectiveDate":"2026-11-20","percentRate":3.88,"targetRateFrom":3.75,"targetRateTo":4.0}]})

class InputsTests(unittest.TestCase):
    def test_exact_market_shapes_and_amount_units(self):
        self.assertEqual(m.trade_rows(FMT,D)["turnover_twd"],1113743193221)
        self.assertEqual(m.trade_rows(OTC,D,True)["turnover_twd"],162025173000)
        with self.assertRaises(m.SourceError): m.trade_rows(OTC,date(2026,11,24),True)
        with self.assertRaises(m.SourceError): m.trade_rows(OTC.replace("不含上櫃股票鉅額交易",""),D,True)
    def test_net_and_query_header_must_reconcile(self):
        self.assertEqual(m.institutions(BFI,D)["twse_inst_net_twd_bn"],-52.103950743)
        with self.assertRaises(m.SourceError): m.institutions(BFI.replace("-16,101,874,546","16,101,874,546"),D)
        with self.assertRaises(m.SourceError): m.institutions(BFI,date(2026,11,24))
    def test_fed_excludes_same_effective_day(self):
        result=m.fed_rates(EFFR,NOW)
        self.assertEqual((result["effective_ffr"],result["target_range"],result["date"]),(3.88,"3.75%–4.00%","2026-11-20"))
    def test_new_sources_integrate_without_replacing_missing_series(self):
        def get(url):
            for k,v in (("FMTQIK",FMT),("tradingIndex",OTC),("BFI82U",BFI),("effr",EFFR)):
                if k in url: return v
            self.fail(url)
        e={"asset_rows":{"台指期夜盤（近月）":{"date":"2026-11-24","close":39829,"source":"https://www.taifex.com.tw/"}},
           "tw_trade_date":"2026-11-23","observations":{"TAIEX":{"close":36811.89}}}
        m.extend(e,NOW,get)
        self.assertEqual(len(e["tw_market_facts"]),6)
        self.assertEqual(e["asset_rows"]["台灣櫃買指數 (TPEx)"]["close"],270.9)
        self.assertEqual(e["tw_market_facts"]["txf_night_close"]["date"],"2026-11-24")
        self.assertNotIn("margin_balance_chg_twd_bn",e["tw_market_facts"])
