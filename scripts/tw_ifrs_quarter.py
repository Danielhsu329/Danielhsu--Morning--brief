"""Taiwan IFRS quarter reconciliation. Offline validation only, no publication adapter."""
from datetime import date, datetime
from decimal import Decimal

def standalone_revenue(quarter, nine_months, six_months):
    if any(type(x) is not int for x in (quarter,nine_months,six_months)):
        raise ValueError("revenue must use integral TWD thousands")
    if min(quarter,six_months)<=0 or quarter!=nine_months-six_months:
        raise ValueError("quarter revenue does not reconcile with YTD")
    return quarter


def quarter_fields(q3, q2, cutoff):
    """Require matching source vintages and scopes; table values are NT$ thousands."""
    if cutoff.tzinfo is None:
        raise ValueError("timezone-aware cutoff required")
    current=date.fromisoformat(q3["period_end"])
    previous=date.fromisoformat(q2["period_end"])
    required_scope=("consolidated","TWD_thousands","cash_purchases_PPE")
    if (current.month,current.day,previous.month,previous.day)!=(9,30,6,30) or current.year!=previous.year:
        raise ValueError("expected same-year Q3/Q2 filings")
    for row in (q3,q2):
        filed=datetime.fromisoformat(row["filed_at"])
        if (filed.tzinfo is None or not date.fromisoformat(row["period_end"]) < filed.date()
            or filed>cutoff or row["scope"]!=required_scope
            or row["fiscal_start"]!=f"{current.year}-01-01" or row["issuer"]!=q3["issuer"]):
            raise ValueError("wrong filing scope, unit, issuer, or release date")
        for field in ("ytd_cfo","ytd_capex_cash_ppe"):
            if type(row[field]) is not int or field.endswith("ppe") and row[field]<0:
                raise ValueError("unreconciled cash-flow input")
    keys=("q_revenue","q_gross_profit","q_operating_income","cash_and_equivalents",
          "ytd_revenue")
    if any(type(q3[x]) is not int for x in keys) or q3["q_revenue"]<=0 or q3["cash_and_equivalents"]<0:
        raise ValueError("invalid standalone quarter fields")
    if "ytd_revenue" in q2:
        standalone_revenue(q3["q_revenue"],q3["ytd_revenue"],q2["ytd_revenue"])
    cfo=q3["ytd_cfo"]-q2["ytd_cfo"]
    capex=q3["ytd_capex_cash_ppe"]-q2["ytd_capex_cash_ppe"]
    if capex<0:
        raise ValueError("cash PP&E flow must reconcile to nonnegative quarter purchases")
    out={"period_start":f"{current.year}-07-01","period_end":current.isoformat(),
         "q_revenue_twd_thousand":q3["q_revenue"],
         "q_cfo_twd_thousand":cfo,"q_capex_twd_thousand":capex,
         "q_fcf_twd_thousand":cfo-capex,
         "cash_equivalents_twd_thousand":q3["cash_and_equivalents"],
         "cash_balance_date":current.isoformat(),
         "gross_margin_pct":round(Decimal(q3["q_gross_profit"])*100/q3["q_revenue"],2),
         "operating_margin_pct":round(Decimal(q3["q_operating_income"])*100/q3["q_revenue"],2),
         "coverage":"fixture_only_no_publication_authority"}
    if all(type(row.get("ytd_contract_liability_effect")) is int for row in (q3,q2)):
        out["q_contract_liability_cfo_effect_twd_thousand"]=(
            q3["ytd_contract_liability_effect"]-q2["ytd_contract_liability_effect"])
    return out
