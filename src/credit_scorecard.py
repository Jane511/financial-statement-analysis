"""
Integrated Credit Scorecard
============================
Weighted pass/fail scorecard combining financial ratios, Z-score, Merton PD,
and working capital quality into a single committee decision.

Maps to the IC_Decision sheet of the AU SME Borrower Model.

Scoring:
  - Each metric has a pass rule, a 1/0 pass flag, and a weight
  - Weighted score = sum(pass_flag * weight) → range 0 to 1
  - Internal grade: A (>=0.80), B (>=0.60), C (>=0.40), D (<0.40)
  - Decision: APPROVE (A/B), REFER (C), DECLINE (D)
"""

import pandas as pd
import numpy as np

from .altman_zscore import compute_zscore_components
from .merton_pd import compute_merton_pd, get_sector_sigma, get_expected_return
from .working_capital import analyse_working_capital
from .trend_analysis import analyse_trends


# Scorecard definition — matches IC_Decision sheet
SCORECARD_RULES = [
    {"metric": "zscore",       "label": "Z-score FY0",           "rule": ">= 1.8",   "threshold": 1.8,  "direction": ">=", "weight": 0.06},
    {"metric": "zscore_trend", "label": "Z-score trend",         "rule": "UP or FLAT","threshold": None, "direction": None, "weight": 0.03},
    {"metric": "debt_to_ebitda","label": "Debt / EBITDA",        "rule": "<= 4.0x",   "threshold": 4.0,  "direction": "<=", "weight": 0.07},
    {"metric": "dscr",         "label": "DSCR",                  "rule": ">= 1.20x",  "threshold": 1.20, "direction": ">=", "weight": 0.09},
    {"metric": "icr",          "label": "ICR (EBIT / Interest)", "rule": ">= 2.0x",   "threshold": 2.0,  "direction": ">=", "weight": 0.07},
    {"metric": "fccr",         "label": "FCCR",                  "rule": ">= 1.20x",  "threshold": 1.20, "direction": ">=", "weight": 0.07},
    {"metric": "current_ratio","label": "Current Ratio",         "rule": ">= 1.20x",  "threshold": 1.20, "direction": ">=", "weight": 0.04},
    {"metric": "quick_ratio",  "label": "Quick Ratio",           "rule": ">= 0.80x",  "threshold": 0.80, "direction": ">=", "weight": 0.04},
    {"metric": "fcf",          "label": "Free Cash Flow FY0",    "rule": "> 0",       "threshold": 0,    "direction": ">",  "weight": 0.09},
    {"metric": "tnw",          "label": "Tangible Net Worth FY0","rule": "> 0",       "threshold": 0,    "direction": ">",  "weight": 0.07},
    {"metric": "merton_pd",    "label": "Merton PD",             "rule": "<= 10%",    "threshold": 0.10, "direction": "<=", "weight": 0.07},
    {"metric": "wc_flag",      "label": "Working Capital Flag",  "rule": "not RED",   "threshold": None, "direction": None, "weight": 0.05},
    {"metric": "sigma",        "label": "Selected Sigma",        "rule": "<= 50%",    "threshold": 0.50, "direction": "<=", "weight": 0.03},
    {"metric": "trend_flags",  "label": "Core Trend Flags",      "rule": ">= 7 of 8", "threshold": 7,   "direction": ">=", "weight": 0.06},
]


def _check_pass(value, direction, threshold) -> int:
    """Evaluate a single pass/fail rule."""
    if value is None or threshold is None or direction is None:
        return 0
    if np.isnan(value) if isinstance(value, float) else False:
        return 0
    if direction == ">=":
        return 1 if value >= threshold else 0
    elif direction == "<=":
        return 1 if value <= threshold else 0
    elif direction == ">":
        return 1 if value > threshold else 0
    elif direction == "<":
        return 1 if value < threshold else 0
    return 0


def score_borrower(df: pd.DataFrame, borrower_id: int, rf: float = 0.0464) -> dict:
    """
    Run the full integrated credit scorecard for a single borrower.

    Parameters
    ----------
    df : pd.DataFrame
        Full dataset with ratio columns (output of ratio_engine.calculate_ratios).
    borrower_id : int
        Borrower to score.
    rf : float
        Risk-free rate for Merton model.

    Returns
    -------
    dict
        Keys: scorecard_table (pd.DataFrame), weighted_score, grade, decision, narrative.
    """
    from .ratio_engine import calculate_ratios

    # Ensure ratios are calculated
    if "dscr" not in df.columns:
        df = calculate_ratios(df)

    fy0 = df[(df["borrower_id"] == borrower_id) & (df["period"] == "FY0")]
    if fy0.empty:
        return {"error": "No FY0 data found"}
    row = fy0.iloc[0]

    # Get derived values
    industry = row["anzsic_division"]
    sigma = get_sector_sigma(industry)
    mu = get_expected_return(industry)

    # Z-score
    zs = compute_zscore_components(row)
    zscore = zs["zscore"]

    # Z-score trend
    from .altman_zscore import borrower_zscore_trend
    zt = borrower_zscore_trend(df, borrower_id)
    zscore_trend = zt.attrs.get("trend", "FLAT")

    # Merton PD
    merton = compute_merton_pd(row["total_assets"], row["total_debt"], sigma, mu, rf)
    merton_pd = merton["pd"]

    # Working capital
    wc = analyse_working_capital(row)
    wc_flag = wc["flag"]

    # Free cash flow and TNW
    fcf = row.get("free_cash_flow", row["operating_cash_flow"] - row["capex"] - row["dividends"])
    tnw = row.get("tangible_net_worth", row["net_worth"] - row["intangible_assets"])

    # Trend flags
    trends = analyse_trends(df, borrower_id)
    positive_count = (trends["status"] == "POSITIVE").sum()

    # Build scorecard
    values = {
        "zscore": zscore,
        "zscore_trend": zscore_trend,
        "debt_to_ebitda": row["debt_to_ebitda"] if "debt_to_ebitda" in row.index else row["total_debt"] / row["ebitda"],
        "dscr": row["dscr"] if "dscr" in row.index else row["ebitda"] / (row["interest_expense"] + row["scheduled_principal"]),
        "icr": row["icr"] if "icr" in row.index else row["ebit"] / row["interest_expense"],
        "fccr": row["fccr"] if "fccr" in row.index else None,
        "current_ratio": row["current_ratio"] if "current_ratio" in row.index else row["current_assets"] / row["current_liabilities"],
        "quick_ratio": row["quick_ratio"] if "quick_ratio" in row.index else (row["cash"] + row["debtors"]) / row["current_liabilities"],
        "fcf": fcf,
        "tnw": tnw,
        "merton_pd": merton_pd,
        "wc_flag": wc_flag,
        "sigma": sigma,
        "trend_flags": positive_count,
    }

    # Score each rule
    rows = []
    for rule in SCORECARD_RULES:
        metric_key = rule["metric"]
        actual = values.get(metric_key)

        # Special handling for non-numeric checks
        if metric_key == "zscore_trend":
            passed = 1 if actual in ("UP", "FLAT") else 0
        elif metric_key == "wc_flag":
            passed = 1 if actual != "RED" else 0
        else:
            passed = _check_pass(actual, rule["direction"], rule["threshold"])

        rows.append({
            "metric": rule["label"],
            "actual": actual,
            "rule": rule["rule"],
            "pass": passed,
            "weight": rule["weight"],
        })

    scorecard_df = pd.DataFrame(rows)
    weighted_score = (scorecard_df["pass"] * scorecard_df["weight"]).sum()
    total_passed = scorecard_df["pass"].sum()

    # Grade
    if weighted_score >= 0.80:
        grade = "A"
    elif weighted_score >= 0.60:
        grade = "B"
    elif weighted_score >= 0.40:
        grade = "C"
    else:
        grade = "D"

    # Decision
    if grade in ("A", "B"):
        decision = "APPROVE"
    elif grade == "C":
        decision = "REFER"
    else:
        decision = "DECLINE"

    # Narrative
    narrative_parts = []
    if zscore >= 1.8:
        narrative_parts.append("Z-score")
    if row.get("dscr", values["dscr"]) >= 1.20:
        narrative_parts.append("DSCR")
    if merton_pd <= 0.10:
        narrative_parts.append("Merton PD")
    if wc_flag != "RED":
        narrative_parts.append("working capital")

    if narrative_parts:
        narrative = f"Updated credit score, {', '.join(narrative_parts)} tests are supportive."
    else:
        narrative = "Multiple credit metrics are below threshold — further review required."

    return {
        "scorecard_table": scorecard_df,
        "weighted_score": round(weighted_score, 4),
        "total_passed": total_passed,
        "total_tests": len(SCORECARD_RULES),
        "grade": grade,
        "decision": decision,
        "narrative": narrative,
        "merton": merton,
        "zscore_detail": zs,
        "wc_detail": wc,
    }


def portfolio_scorecard_summary(df: pd.DataFrame, rf: float = 0.0464) -> pd.DataFrame:
    """
    Score all borrowers and return a portfolio summary.

    Returns
    -------
    pd.DataFrame
        One row per borrower with score, grade, decision.
    """
    from .ratio_engine import calculate_ratios

    df_r = calculate_ratios(df) if "dscr" not in df.columns else df

    results = []
    for bid in df_r["borrower_id"].unique():
        sc = score_borrower(df_r, bid, rf)
        if "error" in sc:
            continue
        results.append({
            "borrower_id": bid,
            "weighted_score": sc["weighted_score"],
            "grade": sc["grade"],
            "decision": sc["decision"],
            "total_passed": sc["total_passed"],
        })
    return pd.DataFrame(results)
