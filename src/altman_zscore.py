"""
Altman Z-Score (SME Proxy)
==========================
Calculates the Altman Z-score using book equity as a proxy for market cap
(since SMEs are not publicly listed). Maps to the Sigma_Final sheet.

Formula (original Altman 1968, adapted for private firms — Z' model):
  Z = 0.717*T1 + 0.847*T2 + 3.107*T3 + 0.420*T4 + 0.998*T5

Where:
  T1 = Working Capital / Total Assets
  T2 = Retained Earnings / Total Assets (proxy: Net Worth - Share Capital)
  T3 = EBIT / Total Assets
  T4 = Book Value of Equity / Total Liabilities (proxy for Market Cap / TL)
  T5 = Sales / Total Assets

Zones:
  Z > 2.99 → SAFE (low default probability)
  1.8 <= Z <= 2.99 → GREY ZONE (moderate risk)
  Z < 1.8 → DISTRESS (high default probability)

Verification: Base-case borrower FY0 should produce Z = 2.885
"""

import pandas as pd
import numpy as np


# Altman Z-score coefficients — using original (1968) formula with book equity proxy
# for market cap (standard approach for unlisted SMEs in AU bank practice).
# The Excel model uses these exact coefficients with T4 = Book Equity / Total Liabilities.
COEFF = {
    "T1": 1.2,
    "T2": 1.4,
    "T3": 3.3,
    "T4": 0.6,
    "T5": 1.0,
}


def compute_zscore_components(row: pd.Series) -> dict:
    """
    Compute the 5 Altman Z-score components for a single borrower-period.

    Parameters
    ----------
    row : pd.Series
        Single row with: working_capital (or current_assets/current_liabilities),
        net_worth, share_capital, ebit, total_assets, total_debt, revenue.

    Returns
    -------
    dict
        T1-T5 components, Z-score, and zone classification.
    """
    ta = row["total_assets"]
    if ta == 0:
        return {"T1": 0, "T2": 0, "T3": 0, "T4": 0, "T5": 0, "zscore": 0, "zone": "DISTRESS"}

    wc = row["current_assets"] - row["current_liabilities"]
    retained_earnings = row["net_worth"] - row["share_capital"]
    total_liabilities = ta - row["net_worth"]

    T1 = wc / ta
    T2 = retained_earnings / ta
    T3 = row["ebit"] / ta
    T4 = row["net_worth"] / total_liabilities if total_liabilities > 0 else 0
    T5 = row["revenue"] / ta

    zscore = (
        COEFF["T1"] * T1
        + COEFF["T2"] * T2
        + COEFF["T3"] * T3
        + COEFF["T4"] * T4
        + COEFF["T5"] * T5
    )

    if zscore > 2.99:
        zone = "SAFE"
    elif zscore >= 1.8:
        zone = "GREY"
    else:
        zone = "DISTRESS"

    return {
        "T1_wc_ta": T1,
        "T2_re_ta": T2,
        "T3_ebit_ta": T3,
        "T4_equity_tl": T4,
        "T5_sales_ta": T5,
        "zscore": round(zscore, 3),
        "zone": zone,
    }


def borrower_zscore_trend(df: pd.DataFrame, borrower_id: int) -> pd.DataFrame:
    """
    Compute Z-score across all 3 periods for a borrower and assess trend.

    Parameters
    ----------
    df : pd.DataFrame
        Full dataset (long format).
    borrower_id : int
        Borrower to analyse.

    Returns
    -------
    pd.DataFrame
        Z-score components and trend for each period.
    """
    bdf = df[df["borrower_id"] == borrower_id].copy()
    bdf["period"] = pd.Categorical(bdf["period"], categories=["FY-2", "FY-1", "FY0"], ordered=True)
    bdf = bdf.sort_values("period")

    rows = []
    for _, row in bdf.iterrows():
        result = compute_zscore_components(row)
        result["period"] = row["period"]
        rows.append(result)

    trend_df = pd.DataFrame(rows).set_index("period")

    # Add trend direction
    scores = trend_df["zscore"].values
    if len(scores) >= 2:
        if scores[-1] > scores[-2]:
            trend_df.attrs["trend"] = "UP"
            trend_df.attrs["trend_comment"] = "Z-score improved in the latest period."
        elif scores[-1] < scores[-2]:
            trend_df.attrs["trend"] = "DOWN"
            trend_df.attrs["trend_comment"] = "Z-score deteriorated in the latest period."
        else:
            trend_df.attrs["trend"] = "FLAT"
            trend_df.attrs["trend_comment"] = "Z-score is stable."

    return trend_df


def portfolio_zscore_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute FY0 Z-scores for all borrowers.

    Returns
    -------
    pd.DataFrame
        One row per borrower with Z-score and zone.
    """
    fy0 = df[df["period"] == "FY0"].copy()
    results = []
    for _, row in fy0.iterrows():
        zs = compute_zscore_components(row)
        results.append({
            "borrower_id": row["borrower_id"],
            "borrower_name": row["borrower_name"],
            "zscore": zs["zscore"],
            "zone": zs["zone"],
        })
    return pd.DataFrame(results)
