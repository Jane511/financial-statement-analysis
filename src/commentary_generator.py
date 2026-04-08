"""
Automated Credit Commentary Generator
=======================================
Generates narrative credit committee comments by consolidating outputs from
all analysis modules. Maps to the Automated_Comments sheet.

Bank credit papers typically include:
  - Borrower overview (industry, size)
  - Trend assessment for key financial metrics
  - Working capital quality commentary
  - Repayment capacity analysis
  - PD / Z-score assessment
  - Pricing justification
  - Recommended covenants
  - Overall recommendation
"""

import pandas as pd
import numpy as np


def generate_borrower_commentary(
    borrower_name: str,
    industry: str,
    revenue_fy0: float,
    scorecard_result: dict,
    trends: pd.DataFrame,
    wc_detail: dict,
    merton: dict,
    zscore_detail: dict,
    pricing: dict,
    period_labels: list[str] | None = None,
) -> str:
    """
    Generate a full credit committee narrative for a single borrower.

    Parameters
    ----------
    borrower_name : str
    industry : str
    revenue_fy0 : float
    scorecard_result : dict
        Output of credit_scorecard.score_borrower().
    trends : pd.DataFrame
        Output of trend_analysis.analyse_trends().
    wc_detail : dict
        Working capital analysis output.
    merton : dict
        Merton PD output.
    zscore_detail : dict
        Z-score components.
    pricing : dict
        Risk-based pricing output.

    Returns
    -------
    str
        Multi-paragraph credit narrative.
    """
    sections = []
    if period_labels is None:
        period_labels = [
            col for col in ["FY-2", "FY-1", "FY0"]
            if col in trends.columns and not trends[col].isna().all()
        ]
    period_descriptor = ", ".join(period_labels) if period_labels else "FY0"

    # 1. Borrower overview
    rev_m = revenue_fy0 / 1_000_000
    sections.append(
        f"BORROWER OVERVIEW\n"
        f"{borrower_name} operates in the {industry} sector with FY0 revenue of "
        f"A${rev_m:,.1f}M. The business has been assessed under the bank's SME "
        f"credit framework using {len(period_labels) if period_labels else 1} "
        f"periods of financial data ({period_descriptor})."
    )

    # 2. Financial trends
    pos_count = (trends["status"] == "POSITIVE").sum()
    neg_count = (trends["status"] == "NEGATIVE").sum()
    total = len(trends)
    trend_text = f"FINANCIAL TRENDS\n{pos_count} of {total} monitored metrics show positive trends."

    neg_items = trends[trends["status"] == "NEGATIVE"]
    if len(neg_items) > 0:
        neg_names = ", ".join(neg_items["metric"].tolist())
        trend_text += f" Negative trends observed in: {neg_names}."
    else:
        trend_text += " No negative trends were identified."
    sections.append(trend_text)

    # 3. Working capital
    wc_text = (
        f"WORKING CAPITAL\n"
        f"Working capital flag: {wc_detail['flag']}. {wc_detail['comment']}. "
        f"Cash represents {wc_detail['cash_share_of_ca']:.0%} of current assets."
    )
    sections.append(wc_text)

    # 4. Repayment capacity
    sc_table = scorecard_result["scorecard_table"]
    dscr_row = sc_table[sc_table["metric"] == "DSCR"]
    icr_row = sc_table[sc_table["metric"] == "ICR (EBIT / Interest)"]
    dscr_val = dscr_row["actual"].values[0] if len(dscr_row) > 0 else "N/A"
    icr_val = icr_row["actual"].values[0] if len(icr_row) > 0 else "N/A"

    capacity_text = (
        f"REPAYMENT CAPACITY\n"
        f"DSCR: {dscr_val:.2f}x (threshold: >= 1.20x). "
        f"ICR: {icr_val:.2f}x (threshold: >= 2.0x). "
    )
    fcf_row = sc_table[sc_table["metric"] == "Free Cash Flow FY0"]
    if len(fcf_row) > 0 and fcf_row["pass"].values[0] == 1:
        capacity_text += "Free cash flow is the primary repayment source, which is preferred."
    else:
        capacity_text += "Free cash flow position warrants monitoring."
    sections.append(capacity_text)

    # 5. Credit quality
    zscore = zscore_detail["zscore"]
    zone = zscore_detail["zone"]
    pd_val = merton["pd"]
    pd_comment = merton["pd_comment"]

    credit_text = (
        f"CREDIT QUALITY\n"
        f"Altman Z-score: {zscore:.3f} ({zone} zone). "
        f"Merton PD: {pd_val:.2%} ({pd_comment}). "
        f"PVEL: A${merton['pvel']:,.0f}."
    )
    sections.append(credit_text)

    # 6. Scorecard and pricing
    score = scorecard_result["weighted_score"]
    grade = scorecard_result["grade"]
    decision = scorecard_result["decision"]
    all_in = pricing["all_in_rate"]

    decision_text = (
        f"SCORECARD & PRICING\n"
        f"Weighted IC score: {score:.2%}. Internal grade: {grade}. "
        f"Decision: {decision}. "
        f"Indicative all-in rate: {all_in:.2%}. {pricing['comment']}"
    )
    sections.append(decision_text)

    # 7. Recommended covenants
    covenant_text = (
        f"RECOMMENDED COVENANTS\n"
        f"- Debt / EBITDA: <= 4.0x (tested semi-annually)\n"
        f"- ICR (EBIT / Interest): >= 2.0x (tested semi-annually)\n"
        f"- DSCR: >= 1.20x (tested annually)\n"
        f"- Provision of annual audited financial statements within 120 days of year-end\n"
        f"- Provision of interim management accounts within 45 days of half-year"
    )
    sections.append(covenant_text)

    return "\n\n".join(sections)


def generate_automated_comments_table(
    scorecard_result: dict,
    trends: pd.DataFrame,
    wc_detail: dict,
    merton: dict,
    zscore_detail: dict,
    pricing: dict,
) -> pd.DataFrame:
    """
    Generate the Automated_Comments table (topic, status, comment, driver).
    Maps directly to the Automated_Comments sheet.
    """
    rows = []

    # Trend-based comments
    for _, t in trends.iterrows():
        rows.append({
            "topic": f"{t['metric']} trend",
            "status": t["status"],
            "comment": t["comment"],
            "driver": t.get("FY0", ""),
        })

    # Working capital
    rows.append({
        "topic": "Working capital quality",
        "status": wc_detail["flag"],
        "comment": wc_detail["comment"],
        "driver": wc_detail["final_wc_incl_cash"],
    })

    # Merton PD
    rows.append({
        "topic": "Merton PD review",
        "status": "GREEN" if merton["pd"] <= 0.05 else ("AMBER" if merton["pd"] <= 0.10 else "RED"),
        "comment": merton["pd_comment"],
        "driver": merton["pd"],
    })

    # Z-score
    rows.append({
        "topic": "Z-score review",
        "status": "GREEN" if zscore_detail["zone"] == "SAFE" else ("AMBER" if zscore_detail["zone"] == "GREY" else "RED"),
        "comment": f"Z-score: {zscore_detail['zscore']:.3f} ({zscore_detail['zone']} zone)",
        "driver": zscore_detail["zscore"],
    })

    # Scorecard
    rows.append({
        "topic": "IC decision",
        "status": "GREEN" if scorecard_result["decision"] == "APPROVE" else "RED",
        "comment": scorecard_result["decision"],
        "driver": scorecard_result["grade"],
    })

    # Pricing
    rows.append({
        "topic": "Risk-based pricing",
        "status": "GREEN" if pricing["all_in_rate"] <= 0.12 else "AMBER",
        "comment": pricing["comment"],
        "driver": pricing["all_in_rate"],
    })

    return pd.DataFrame(rows)
