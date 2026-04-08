"""
Three-Period Trend Analysis
============================
Calculates slopes and direction flags across FY-2 → FY-1 → FY0 for key metrics.
Maps to the Derived_Ratios sheet rows 23-40 (Lecture-required three-period trend review).

Bank credit analysts assess whether key financial metrics are improving, stable, or
deteriorating. This module produces:
  - Linear slope across 3 periods
  - Direction flag: POSITIVE / NEGATIVE / FLAT
  - Automated narrative comment (for credit papers)
"""

import pandas as pd
import numpy as np


# Metrics where a DECREASE is positive (e.g. Debt/EBITDA going down is good)
INVERSE_METRICS = {
    "debt_to_ebitda", "debt_to_cashflow", "debt_to_assets", "debt_to_equity",
    "net_leverage", "payback_ratio", "debtor_days", "inventory_days",
}

# Labels for display
METRIC_LABELS = {
    "revenue": "Revenue",
    "ebitda": "EBITDA / PBDIT",
    "ebitda_margin": "EBITDA Margin",
    "ebit": "EBIT / Operating Profit",
    "operating_cash_flow": "Operating Cash Flow",
    "net_worth": "Net Worth / Total Equity",
    "share_capital": "Equity Infusion / Share Capital",
    "cash": "Liquidity (Cash in Hand)",
    "working_capital": "Working Capital",
    "debt_to_ebitda": "Debt / EBITDA",
    "debt_to_cashflow": "Debt / Cash Flow",
    "icr": "Interest Coverage (EBIT / Interest)",
    "ebitda_icr": "EBITDA Interest Coverage",
    "current_ratio": "Current Ratio",
    "dscr": "DSCR",
    "fccr": "FCCR",
    "free_cash_flow": "Free Cash Flow",
    "tangible_net_worth": "Tangible Net Worth",
}

# Auto-comment templates
POSITIVE_COMMENTS = {
    "revenue": "Revenue trend is increasing across the 3 observed periods.",
    "ebitda": "EBITDA/PBDIT is improving, consistent with stronger operating earnings.",
    "ebitda_margin": "EBITDA margin is expanding.",
    "ebit": "Operating profit is increasing.",
    "operating_cash_flow": "Operating cash flow is improving, matching the lectures cash-flow test.",
    "net_worth": "Net worth is increasing, which is supportive of credit quality.",
    "share_capital": "Equity infusion is increasing, indicating greater support from shareholders / owners.",
    "cash": "Cash on hand is increasing, which supports day-to-day liquidity.",
    "working_capital": "Working capital is positive and improving.",
    "debt_to_ebitda": "Debt / EBITDA is trending down, which is supportive for credit.",
    "debt_to_cashflow": "Debt / Cash Flow is trending down, which is supportive for repayment capacity.",
    "icr": "Interest coverage is improving.",
    "current_ratio": "Current ratio is improving.",
    "free_cash_flow": "Free cash flow is improving, supporting internal debt repayment.",
    "tangible_net_worth": "Tangible net worth remains positive, showing real balance-sheet support.",
}

NEGATIVE_COMMENTS = {
    "revenue": "Revenue is declining, which warrants further investigation.",
    "ebitda": "EBITDA/PBDIT is deteriorating — earnings quality may be weakening.",
    "ebitda_margin": "EBITDA margin is compressing.",
    "ebit": "Operating profit is declining.",
    "operating_cash_flow": "Operating cash flow is deteriorating.",
    "net_worth": "Net worth is declining, reducing balance-sheet support.",
    "debt_to_ebitda": "Debt / EBITDA is increasing, indicating rising leverage.",
    "debt_to_cashflow": "Debt / Cash Flow is increasing, which may stress repayment capacity.",
    "icr": "Interest coverage is declining.",
    "free_cash_flow": "Free cash flow is deteriorating.",
}


def compute_slope(values: np.ndarray) -> float:
    """Simple linear slope across 3 equally-spaced periods."""
    if len(values) < 2 or np.any(np.isnan(values)):
        return np.nan
    x = np.arange(len(values), dtype=float)
    return np.polyfit(x, values, 1)[0]


def classify_trend(slope: float, metric: str, threshold: float = 1e-6) -> str:
    """
    Classify trend direction.

    For inverse metrics (where decline is good), a negative slope = POSITIVE.
    """
    if np.isnan(slope):
        return "INSUFFICIENT DATA"

    is_inverse = metric in INVERSE_METRICS

    if abs(slope) < threshold:
        return "FLAT"
    elif slope > 0:
        return "NEGATIVE" if is_inverse else "POSITIVE"
    else:
        return "POSITIVE" if is_inverse else "NEGATIVE"


def get_auto_comment(metric: str, status: str) -> str:
    """Return automated narrative comment for the trend."""
    if status == "POSITIVE":
        return POSITIVE_COMMENTS.get(metric, f"{METRIC_LABELS.get(metric, metric)} trend is positive.")
    elif status == "NEGATIVE":
        return NEGATIVE_COMMENTS.get(metric, f"{METRIC_LABELS.get(metric, metric)} trend is negative.")
    elif status == "FLAT":
        return f"{METRIC_LABELS.get(metric, metric)} is broadly stable."
    return ""


def analyse_trends(
    df_with_ratios: pd.DataFrame,
    borrower_id: int,
    metrics: list[str] | None = None,
) -> pd.DataFrame:
    """
    Perform 3-period trend analysis for a single borrower.

    Parameters
    ----------
    df_with_ratios : pd.DataFrame
        Dataset with ratio columns (output of ratio_engine.calculate_ratios).
    borrower_id : int
        Borrower to analyse.
    metrics : list[str], optional
        Subset of metrics to analyse. Defaults to core lecture-aligned metrics.

    Returns
    -------
    pd.DataFrame
        Trend table with columns: metric, FY-2, FY-1, FY0, slope, status, comment, pass.
    """
    if metrics is None:
        metrics = [
            "revenue", "ebitda", "ebitda_margin", "ebit",
            "working_capital", "debt_to_ebitda", "debt_to_cashflow",
            "icr", "current_ratio", "operating_cash_flow",
            "cash", "net_worth", "share_capital", "free_cash_flow",
        ]

    bdf = df_with_ratios[df_with_ratios["borrower_id"] == borrower_id].copy()
    bdf["period"] = pd.Categorical(bdf["period"], categories=["FY-2", "FY-1", "FY0"], ordered=True)
    bdf = bdf.sort_values("period")

    rows = []
    for metric in metrics:
        if metric not in bdf.columns:
            continue
        values = bdf[metric].values.astype(float)
        slope = compute_slope(values)
        status = classify_trend(slope, metric)
        comment = get_auto_comment(metric, status)
        passed = 1 if status == "POSITIVE" else 0

        rows.append({
            "metric": METRIC_LABELS.get(metric, metric),
            "metric_key": metric,
            "FY-2": values[0] if len(values) > 0 else np.nan,
            "FY-1": values[1] if len(values) > 1 else np.nan,
            "FY0": values[2] if len(values) > 2 else np.nan,
            "slope": slope,
            "status": status,
            "comment": comment,
            "pass": passed,
        })

    return pd.DataFrame(rows)


def portfolio_trend_summary(df_with_ratios: pd.DataFrame) -> pd.DataFrame:
    """
    Summarise trend flags across all borrowers in the portfolio.

    Returns
    -------
    pd.DataFrame
        Borrower-level summary: count of POSITIVE / NEGATIVE / FLAT flags.
    """
    results = []
    for bid in df_with_ratios["borrower_id"].unique():
        trends = analyse_trends(df_with_ratios, bid)
        pos = (trends["status"] == "POSITIVE").sum()
        neg = (trends["status"] == "NEGATIVE").sum()
        flat = (trends["status"] == "FLAT").sum()
        total = len(trends)
        results.append({
            "borrower_id": bid,
            "positive_flags": pos,
            "negative_flags": neg,
            "flat_flags": flat,
            "total_metrics": total,
            "positive_pct": pos / total if total > 0 else 0,
        })
    return pd.DataFrame(results)
