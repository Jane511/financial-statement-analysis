"""
Working Capital Quality Analysis
=================================
Implements the bank-aligned working capital assessment from the
Working_Capital_Analysis sheet of the AU SME Borrower Model.

Assessment flow:
  1. Remove cash from current assets
  2. Test the raw WC gap (CA excl cash - CL)
  3. Add cash back → final WC
  4. Check if borrowing is needed to make WC positive
  5. Analyse composition (cash share, debtor share, inventory share)
  6. Determine if debt is supporting WC deficits vs expansion/growth

Output: Traffic-light flag (GREEN / AMBER / RED) and analyst commentary.
"""

import pandas as pd
import numpy as np


def analyse_working_capital(row: pd.Series) -> dict:
    """
    Perform bank-aligned working capital analysis for a single borrower-period.

    Parameters
    ----------
    row : pd.Series
        A single row from the dataset containing: current_assets, cash, debtors,
        inventory, current_liabilities, total_debt.

    Returns
    -------
    dict
        Working capital metrics and assessment.
    """
    ca = row["current_assets"]
    cash = row["cash"]
    debtors = row["debtors"]
    inventory = row["inventory"]
    cl = row["current_liabilities"]
    total_debt = row["total_debt"]

    # Step 1: CA excluding cash
    ca_excl_cash = ca - cash

    # Other CA (not cash, debtors, or inventory)
    other_ca = ca_excl_cash - debtors - inventory

    # Step 2: Raw WC gap (before cash)
    raw_wc_excl_cash = ca_excl_cash - cl

    # Step 3: Final WC including cash
    final_wc = ca - cl

    # Step 4: Borrowing required to make WC positive
    borrowing_required = max(-raw_wc_excl_cash, 0)
    borrowing_indicator = -raw_wc_excl_cash  # negative = no borrowing needed

    # Step 5: Cash coverage of raw WC gap
    if raw_wc_excl_cash < 0:
        cash_coverage = cash / abs(raw_wc_excl_cash) if abs(raw_wc_excl_cash) > 0 else 999
    else:
        cash_coverage = 999  # no gap to cover

    # Composition analysis
    cash_share = cash / ca if ca > 0 else 0
    debtor_share = debtors / ca if ca > 0 else 0
    inventory_share = inventory / ca if ca > 0 else 0

    # Step 6: Is debt funding WC?
    debt_for_wc = "Yes — debt appears to be supporting WC" if (final_wc < 0 or borrowing_required > 0) else "No — debt can be viewed as growth/expansion capital"

    # Traffic light flag
    if final_wc > 0 and raw_wc_excl_cash >= 0:
        flag = "GREEN"
        comment = "Positive WC supported by cash; debt not needed for short-term support"
    elif final_wc > 0 and raw_wc_excl_cash < 0 and cash_coverage >= 1.0:
        flag = "AMBER"
        comment = "WC positive only after including cash; underlying gap exists but cash covers it"
    elif final_wc > 0 and raw_wc_excl_cash < 0 and cash_coverage < 1.0:
        flag = "AMBER"
        comment = "WC positive but cash does not fully cover the underlying gap"
    else:
        flag = "RED"
        comment = "Negative working capital — borrowing required for short-term liquidity"

    return {
        "current_assets": ca,
        "cash": cash,
        "debtors": debtors,
        "inventory": inventory,
        "other_ca": other_ca,
        "current_liabilities": cl,
        "ca_excl_cash": ca_excl_cash,
        "raw_wc_excl_cash": raw_wc_excl_cash,
        "final_wc_incl_cash": final_wc,
        "borrowing_required": borrowing_required,
        "borrowing_indicator": borrowing_indicator,
        "cash_coverage_of_gap": cash_coverage,
        "cash_share_of_ca": cash_share,
        "debtor_share_of_ca": debtor_share,
        "inventory_share_of_ca": inventory_share,
        "debt_funding_wc": debt_for_wc,
        "flag": flag,
        "comment": comment,
    }


def borrower_wc_analysis(
    df: pd.DataFrame,
    borrower_id: int,
) -> pd.DataFrame:
    """
    Working capital analysis across all 3 periods for a single borrower.

    Returns
    -------
    pd.DataFrame
        Rows = WC metrics, Columns = FY-2, FY-1, FY0.
    """
    bdf = df[df["borrower_id"] == borrower_id].copy()
    bdf["period"] = pd.Categorical(bdf["period"], categories=["FY-2", "FY-1", "FY0"], ordered=True)
    bdf = bdf.sort_values("period")

    results = {}
    for _, row in bdf.iterrows():
        wc = analyse_working_capital(row)
        results[row["period"]] = wc

    wc_df = pd.DataFrame(results)

    # Select key display rows
    display_rows = [
        "current_assets", "cash", "debtors", "inventory", "other_ca",
        "current_liabilities", "ca_excl_cash", "raw_wc_excl_cash",
        "final_wc_incl_cash", "borrowing_required", "cash_coverage_of_gap",
        "cash_share_of_ca", "debtor_share_of_ca", "inventory_share_of_ca",
        "flag", "comment",
    ]
    return wc_df.loc[display_rows]


def portfolio_wc_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute FY0 working capital flags for all borrowers.

    Returns
    -------
    pd.DataFrame
        One row per borrower with WC flag and key metrics.
    """
    fy0 = df[df["period"] == "FY0"].copy()
    results = []
    for _, row in fy0.iterrows():
        wc = analyse_working_capital(row)
        results.append({
            "borrower_id": row["borrower_id"],
            "borrower_name": row["borrower_name"],
            "final_wc": wc["final_wc_incl_cash"],
            "raw_wc_excl_cash": wc["raw_wc_excl_cash"],
            "cash_share": wc["cash_share_of_ca"],
            "flag": wc["flag"],
            "comment": wc["comment"],
        })
    return pd.DataFrame(results)
