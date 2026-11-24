"""Reconcile disclosed 3131 figures transcribed from mirrors, not exchange byte verification."""
from datetime import datetime, timezone
from decimal import Decimal
import unittest
from tw_ifrs_quarter import quarter_fields, standalone_revenue

CORE={"issuer":"3131","fiscal_start":"2026-01-01","scope":("consolidated","TWD_thousands","cash_purchases_PPE")}
Q3={**CORE,"period_end":"2026-09-30","filed_at":"2026-11-13T00:51:18+00:00",
    "q_revenue":2221360,"q_gross_profit":812736,"q_operating_income":487914,"cash_and_equivalents":5378238,
    "ytd_revenue":5544268,"ytd_cfo":2053751,"ytd_capex_cash_ppe":1232906}
Q2={**CORE,"period_end":"2026-06-30","filed_at":"2026-08-13T01:45:04+00:00",
    "ytd_cfo":673286,"ytd_capex_cash_ppe":1170867}
CUTOFF=datetime(2026,11,24,tzinfo=timezone.utc)

class QuarterTests(unittest.TestCase):
    def test_3131_income_flows_and_point_in_time_cash(self):
        out=quarter_fields(Q3,Q2,CUTOFF)
        self.assertEqual((out["q_cfo_twd_thousand"],out["q_capex_twd_thousand"],
                          out["q_fcf_twd_thousand"]),(1380465,62039,1318426))
        self.assertEqual((out["gross_margin_pct"],out["operating_margin_pct"]),
                         (Decimal("36.59"),Decimal("21.96")))
        self.assertEqual(out["cash_equivalents_twd_thousand"],5378238)
        self.assertEqual(out["cash_balance_date"],"2026-09-30")
        self.assertEqual(out["coverage"],"fixture_only_no_publication_authority")

    def test_reject_ytd_as_quarter_and_bad_scope_or_cutoff(self):
        for current, prior, cutoff in (
            ({**Q3,"q_revenue":5544268},{**Q2,"ytd_revenue":3322908},CUTOFF),
            (Q3,{**Q2,"scope":("consolidated","TWD_billions","cash_purchases_PPE")},CUTOFF),
            (Q3,{**Q2,"fiscal_start":"2026-04-01"},CUTOFF),
            (Q3,Q2,datetime(2026,11,13,0,51,17,tzinfo=timezone.utc))):
            with self.assertRaises(ValueError):
                quarter_fields(current,prior,cutoff)

    def test_3017_and_3583_mirrored_quarter_not_nine_months(self):
        # Six-month values here are implied by the Q3 table columns, not an independent filing.
        for quarter,nine in ((59089348,157248258),(3080473,9195838)):
            self.assertEqual(standalone_revenue(quarter,nine,nine-quarter),quarter)
            with self.assertRaises(ValueError):
                standalone_revenue(nine,nine,nine-quarter)

if __name__=="__main__":
    unittest.main()
