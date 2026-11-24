import json
import unittest
from datetime import datetime, timezone
from tw_monthly_revenue import parse, collect, FEEDS, TICKER, PERIOD, ISSUED, REV, PRIOR, YOY

class MonthRevenueTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,24,8,tzinfo=timezone.utc)
        self.url=FEEDS[0][0]
        self.rows=[{TICKER:code, PERIOD:"11510", ISSUED:"1151117", REV:val, PRIOR:prior, YOY:yoy}
                   for code,val,prior,yoy in (("3131","752995","576826","30.5410990489333"),
                                              ("3324","3372007","2329545","44.74959702431161"))]

    def test_exact_exchange_snapshot(self):
        d=parse(json.dumps(self.rows),("3131","3324"),self.now,self.url)
        self.assertEqual(d["3131.TW"]["revenue_twd_bn"],0.752995)
        self.assertEqual(d["3324.TW"]["yoy_display"],"+44.7%")
        self.assertEqual(d["3324.TW"]["table_date"],"2026-11-17")
        self.assertEqual(d["3131.TW"]["period"],"2026-10")

    def test_not_same_day_stale_duplicate_or_conflicting(self):
        for field,val in ((ISSUED,"1151124"),(PERIOD,"11509"),(YOY,"68.81643921026671")):
            row=dict(self.rows[0],**{field:val})
            self.assertFalse(parse(json.dumps([row]),("3131",),self.now,self.url))
        self.assertFalse(parse(json.dumps([self.rows[0]]*2),("3131",),self.now,self.url))

    def test_absence_does_not_fill_other_exchange(self):
        d,gaps=collect(self.now,lambda url: json.dumps(self.rows) if url==self.url else "")
        self.assertEqual(len(d),2)
        self.assertEqual(set(gaps),{"2330.TW","3583.TW","3017.TW"})
