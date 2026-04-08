"""
Financial Statement Spreading
=============================
Converts raw borrower financial data into a standardised side-by-side template
(FY-2, FY-1, FY0) — the first step in any bank credit analysis.

Maps to the Company_Inputs sheet of the AU SME Borrower Model.
Aligns with standard bank credit framework: "Find the Revenue → Understand Gross Margin →
Normalise Earnings → Total Available for Servicing".
"""

import pandas as pd


# Standardised line-item ordering for the spread template
INCOME_STATEMENT_LINES = [
    "revenue",
    "ebitda",
    "ebit",
    "interest_expense",
    "npat",
]

BALANCE_SHEET_LINES = [
    "cash",
    "debtors",
    "inventory",
    "current_assets",
    "current_liabilities",
    "total_assets",
    "total_debt",
    "intangible_assets",
    "share_capital",
    "net_worth",
]

CASH_FLOW_LINES = [
    "operating_cash_flow",
    "capex",
    "dividends",
    "scheduled_principal",
    "lease_fixed_charges",
    "tax_paid",
]

PERIOD_ORDER = ["FY-2", "FY-1", "FY0"]


def _available_periods(periods: list[str]) -> list[str]:
    """Return known period labels in display order."""
    return [period for period in PERIOD_ORDER if period in periods]


def spread_borrower(df: pd.DataFrame, borrower_id: int) -> pd.DataFrame:
    """
    Pivot a single borrower's long-format data into a wide spread template.

    Parameters
    ----------
    df : pd.DataFrame
        Full dataset (all borrowers, long format).
    borrower_id : int
        The borrower to spread.

    Returns
    -------
    pd.DataFrame
        Wide-format DataFrame with line items as rows and periods as columns.
    """
    bdf = df[df["borrower_id"] == borrower_id].copy()
    bdf["period"] = pd.Categorical(bdf["period"], categories=PERIOD_ORDER, ordered=True)
    bdf = bdf.sort_values("period")
    periods = _available_periods(bdf["period"].astype(str).tolist())

    all_lines = INCOME_STATEMENT_LINES + BALANCE_SHEET_LINES + CASH_FLOW_LINES
    spread = bdf.set_index("period")[all_lines].T
    spread = spread.reindex(columns=periods)
    spread.index.name = "line_item"
    return spread


def spread_all_borrowers(df: pd.DataFrame) -> dict[int, pd.DataFrame]:
    """Spread every borrower in the dataset. Returns dict keyed by borrower_id."""
    result = {}
    for bid in df["borrower_id"].unique():
        result[bid] = spread_borrower(df, bid)
    return result


def format_spread_display(spread: pd.DataFrame, borrower_name: str = "") -> pd.DataFrame:
    """
    Format spread for display — numbers in A$ thousands with commas.

    Parameters
    ----------
    spread : pd.DataFrame
        Output of spread_borrower().
    borrower_name : str
        Optional name for display header.

    Returns
    -------
    pd.DataFrame
        Formatted string DataFrame suitable for notebook display.
    """
    display_df = spread.copy()

    # Section labels
    sections = {}
    for item in INCOME_STATEMENT_LINES:
        sections[item] = "Income Statement"
    for item in BALANCE_SHEET_LINES:
        sections[item] = "Balance Sheet"
    for item in CASH_FLOW_LINES:
        sections[item] = "Cash Flow"

    display_df.insert(0, "section", display_df.index.map(sections))

    # Pretty labels
    label_map = {
        "revenue": "Revenue",
        "ebitda": "EBITDA / PBDIT",
        "ebit": "EBIT / Operating Profit",
        "interest_expense": "Interest Expense",
        "npat": "Net Profit After Tax",
        "cash": "Cash",
        "debtors": "Trade Receivables",
        "inventory": "Inventory",
        "current_assets": "Current Assets",
        "current_liabilities": "Current Liabilities",
        "total_assets": "Total Assets",
        "total_debt": "Total Debt",
        "intangible_assets": "Intangible Assets",
        "share_capital": "Share Capital",
        "net_worth": "Net Worth / Total Equity",
        "operating_cash_flow": "Operating Cash Flow",
        "capex": "Capital Expenditure",
        "dividends": "Dividends / Distributions",
        "scheduled_principal": "Scheduled Principal Repayment",
        "lease_fixed_charges": "Lease / Fixed Charges",
        "tax_paid": "Tax Paid",
    }
    display_df.index = display_df.index.map(lambda x: label_map.get(x, x))

    # Format numbers as A$'000
    for col in _available_periods(display_df.columns.astype(str).tolist()):
        display_df[col] = display_df[col].apply(lambda x: f"${x / 1000:,.0f}k" if pd.notna(x) else "")

    return display_df
