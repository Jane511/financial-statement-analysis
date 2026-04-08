"""
Financial Ratio Engine
======================
Calculates 20+ credit-relevant ratios from standardised financial statements.
Maps directly to the Derived_Ratios sheet of the AU SME Borrower Model.

Ratio categories match what banks assess for commercial cash flow lending:
  - Profitability (margins, returns)
  - Leverage (debt capacity)
  - Coverage (repayment ability — the "first way out")
  - Liquidity (short-term solvency)
  - Efficiency (asset utilisation)
  - Growth (revenue and earnings momentum)

Aligns with standard bank credit framework "Four Measures of Capacity":
  1. ICR (Interest Cover Ratio)
  2. DSCR (Debt Service Cover Ratio)
  3. Payback / Debt Ratio
  4. Multiple of Earnings
"""

import pandas as pd
import numpy as np


def _safe_divide(a, b, default=np.nan):
    """Element-wise division returning default where denominator is zero."""
    return np.where(np.abs(b) > 0, a / b, default)


def calculate_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate all credit ratios for each borrower-period row.

    Parameters
    ----------
    df : pd.DataFrame
        Long-format dataset with one row per borrower-period.

    Returns
    -------
    pd.DataFrame
        Original DataFrame with ratio columns appended.
    """
    out = df.copy()

    # --- Profitability ---
    out["ebitda_margin"] = _safe_divide(out["ebitda"], out["revenue"])
    out["ebit_margin"] = _safe_divide(out["ebit"], out["revenue"])
    out["net_margin"] = _safe_divide(out["npat"], out["revenue"])
    out["ocf_margin"] = _safe_divide(out["operating_cash_flow"], out["revenue"])
    out["roa"] = _safe_divide(out["npat"], out["total_assets"])
    out["roe"] = _safe_divide(out["npat"], out["net_worth"])

    # --- Leverage ---
    out["debt_to_ebitda"] = _safe_divide(out["total_debt"], out["ebitda"])
    out["debt_to_cashflow"] = _safe_divide(out["total_debt"], out["operating_cash_flow"])
    out["debt_to_assets"] = _safe_divide(out["total_debt"], out["total_assets"])
    out["debt_to_equity"] = _safe_divide(out["total_debt"], out["net_worth"])
    out["net_debt"] = out["total_debt"] - out["cash"]
    out["net_leverage"] = _safe_divide(out["net_debt"], out["ebitda"])

    # --- Coverage (the "Four Measures of Capacity") ---
    # 1. ICR — Interest Cover Ratio (EBIT / Interest)
    #    bank credit framework: "EBITO / Total Interest"
    out["icr"] = _safe_divide(out["ebit"], out["interest_expense"])

    # EBITDA-based interest coverage (used in Derived_Ratios sheet)
    out["ebitda_icr"] = _safe_divide(out["ebitda"], out["interest_expense"])

    # 2. DSCR — Debt Service Cover Ratio
    #    Excel model: OCF / (Interest + Scheduled Principal)
    #    Measures actual cash available to meet total debt service obligations.
    total_debt_service = out["interest_expense"] + out["scheduled_principal"]
    out["dscr"] = _safe_divide(out["operating_cash_flow"], total_debt_service)

    # 3. Payback / Debt Ratio — (Total Debt - Cash) / EBITDA
    #    bank credit framework: "Total Proposed Debt - Cash / Total EBITDAO"
    out["payback_ratio"] = _safe_divide(out["total_debt"] - out["cash"], out["ebitda"])

    # 4. Fixed Charge Coverage Ratio (FCCR)
    #    EBITDA / (Interest + Lease/Fixed Charges + Tax + Scheduled Principal)
    total_fixed_charges = (
        out["interest_expense"]
        + out["lease_fixed_charges"]
        + out["tax_paid"]
        + out["scheduled_principal"]
    )
    out["fccr"] = _safe_divide(out["ebitda"], total_fixed_charges)

    # --- Liquidity ---
    out["current_ratio"] = _safe_divide(out["current_assets"], out["current_liabilities"])
    out["quick_ratio"] = _safe_divide(
        out["cash"] + out["debtors"],
        out["current_liabilities"],
    )
    out["working_capital"] = out["current_assets"] - out["current_liabilities"]

    # --- Efficiency ---
    out["debtor_days"] = _safe_divide(out["debtors"] * 365, out["revenue"])
    out["inventory_days"] = _safe_divide(out["inventory"] * 365, out["revenue"])

    # --- Free Cash Flow ---
    out["free_cash_flow"] = (
        out["operating_cash_flow"] - out["capex"] - out["dividends"]
    )

    # --- Tangible Net Worth ---
    out["tangible_net_worth"] = out["net_worth"] - out["intangible_assets"]

    return out


def get_ratio_columns() -> list[str]:
    """Return the list of ratio column names added by calculate_ratios."""
    return [
        "ebitda_margin", "ebit_margin", "net_margin", "ocf_margin", "roa", "roe",
        "debt_to_ebitda", "debt_to_cashflow", "debt_to_assets", "debt_to_equity",
        "net_debt", "net_leverage",
        "icr", "ebitda_icr", "dscr", "payback_ratio", "fccr",
        "current_ratio", "quick_ratio", "working_capital",
        "debtor_days", "inventory_days",
        "free_cash_flow", "tangible_net_worth",
    ]


def borrower_ratio_summary(df_with_ratios: pd.DataFrame, borrower_id: int) -> pd.DataFrame:
    """
    Extract a single borrower's ratios pivoted by period for display.

    Returns
    -------
    pd.DataFrame
        Rows = ratio names, Columns = FY-2, FY-1, FY0.
    """
    bdf = df_with_ratios[df_with_ratios["borrower_id"] == borrower_id].copy()
    bdf["period"] = pd.Categorical(bdf["period"], categories=["FY-2", "FY-1", "FY0"], ordered=True)
    bdf = bdf.sort_values("period")

    ratio_cols = get_ratio_columns()
    summary = bdf.set_index("period")[ratio_cols].T
    summary.index.name = "ratio"
    return summary


# Bank threshold reference — used for display and scorecard
BANK_THRESHOLDS = {
    "icr": {"label": "ICR (EBIT / Interest)", "pass": ">= 2.0x", "threshold": 2.0, "direction": ">="},
    "dscr": {"label": "DSCR", "pass": ">= 1.20x", "threshold": 1.20, "direction": ">="},
    "fccr": {"label": "FCCR", "pass": ">= 1.20x", "threshold": 1.20, "direction": ">="},
    "debt_to_ebitda": {"label": "Debt / EBITDA", "pass": "<= 4.0x", "threshold": 4.0, "direction": "<="},
    "current_ratio": {"label": "Current Ratio", "pass": ">= 1.20x", "threshold": 1.20, "direction": ">="},
    "quick_ratio": {"label": "Quick Ratio", "pass": ">= 0.80x", "threshold": 0.80, "direction": ">="},
    "debt_to_assets": {"label": "Debt / Assets", "pass": "<= 0.60", "threshold": 0.60, "direction": "<="},
}
