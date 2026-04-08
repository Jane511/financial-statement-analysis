"""
Risk-Based Pricing Engine
==========================
Calculates indicative all-in lending rate based on PD, expected loss,
and borrower risk profile. Maps to the Risk_Based_Pricing sheet.

Pricing structure (aligns with standard bank credit framework — Interest Rate Components):
  1. Base rate (risk-free rate / BBSY proxy)
  2. Funding spread (bank's cost of wholesale funding above risk-free)
  3. Operating / servicing spread (admin costs)
  4. Capital / target return spread (ROE hurdle)
  5. Model overlays:
     - PVEL spread (expected loss priced into margin)
     - Credit score overlay (lower score → higher margin)
     - PD overlay (higher PD → higher margin)
     - Leverage overlay (Debt/EBITDA driven)
     - Liquidity overlay (working capital quality)
     - ICR/DSCR overlay (cash flow serviceability)
"""

import numpy as np
import pandas as pd


# Default pricing policy inputs
DEFAULT_PRICING_PARAMS = {
    "rf": 0.0464,               # Base risk-free rate (AU proxy)
    "funding_spread": 0.020,    # Bank funding spread
    "operating_spread": 0.015,  # Operating/admin costs
    "capital_spread": 0.015,    # Target return on capital
    "min_margin_floor": 0.010,  # Minimum margin floor
}


def compute_pricing(
    facility_amount: float,
    pd_value: float,
    pvel: float,
    weighted_score: float,
    debt_to_ebitda: float,
    wc_flag: str,
    icr: float,
    dscr: float,
    params: dict | None = None,
) -> dict:
    """
    Compute risk-based indicative pricing for a facility.

    Parameters
    ----------
    facility_amount : float
        EAD / facility amount (A$).
    pd_value : float
        Merton PD.
    pvel : float
        Present Value of Expected Loss (A$).
    weighted_score : float
        Credit scorecard weighted score (0-1).
    debt_to_ebitda : float
        Leverage ratio.
    wc_flag : str
        Working capital flag (GREEN/AMBER/RED).
    icr : float
        Interest coverage ratio.
    dscr : float
        Debt service coverage ratio.
    params : dict, optional
        Override default pricing parameters.

    Returns
    -------
    dict
        Pricing breakdown and all-in rate.
    """
    p = {**DEFAULT_PRICING_PARAMS, **(params or {})}

    # PVEL spread — core structural expected-loss spread
    pvel_spread = pvel / facility_amount if facility_amount > 0 else 0

    # Credit score overlay — lower score requires extra margin
    if weighted_score >= 0.80:
        score_overlay = 0.0
    elif weighted_score >= 0.60:
        score_overlay = 0.005
    elif weighted_score >= 0.40:
        score_overlay = 0.015
    else:
        score_overlay = 0.030

    # PD overlay — higher PD requires extra margin
    if pd_value <= 0.01:
        pd_overlay = 0.0
    elif pd_value <= 0.05:
        pd_overlay = 0.005
    elif pd_value <= 0.10:
        pd_overlay = 0.015
    else:
        pd_overlay = 0.025

    # Leverage overlay — Debt/EBITDA based
    if debt_to_ebitda <= 2.0:
        leverage_overlay = 0.0
    elif debt_to_ebitda <= 4.0:
        leverage_overlay = 0.005
    elif debt_to_ebitda <= 6.0:
        leverage_overlay = 0.015
    else:
        leverage_overlay = 0.025

    # Liquidity overlay — working capital quality
    if wc_flag == "GREEN":
        liquidity_overlay = 0.0
    elif wc_flag == "AMBER":
        liquidity_overlay = 0.005
    else:
        liquidity_overlay = 0.015

    # ICR/DSCR overlay — cash flow serviceability
    if icr >= 3.0 and dscr >= 1.5:
        coverage_overlay = 0.0
    elif icr >= 2.0 and dscr >= 1.2:
        coverage_overlay = 0.005
    else:
        coverage_overlay = 0.015

    # Total model margin
    total_margin = (
        p["funding_spread"]
        + p["operating_spread"]
        + p["capital_spread"]
        + pvel_spread
        + score_overlay
        + pd_overlay
        + leverage_overlay
        + liquidity_overlay
        + coverage_overlay
    )

    total_margin = max(total_margin, p["min_margin_floor"])

    # All-in rate
    all_in_rate = p["rf"] + total_margin

    # Comment
    if all_in_rate <= 0.10:
        comment = "Pricing reflects strong credit quality."
    elif all_in_rate <= 0.15:
        comment = "Pricing is within a normal SME risk range."
    else:
        comment = "Elevated pricing reflects higher credit risk."

    return {
        "facility_amount": facility_amount,
        "base_rate": p["rf"],
        "funding_spread": p["funding_spread"],
        "operating_spread": p["operating_spread"],
        "capital_spread": p["capital_spread"],
        "pvel_spread": pvel_spread,
        "score_overlay": score_overlay,
        "pd_overlay": pd_overlay,
        "leverage_overlay": leverage_overlay,
        "liquidity_overlay": liquidity_overlay,
        "coverage_overlay": coverage_overlay,
        "total_margin": total_margin,
        "all_in_rate": all_in_rate,
        "comment": comment,
    }


def pricing_waterfall_table(pricing: dict) -> pd.DataFrame:
    """
    Format pricing output as a waterfall table for display.

    Returns
    -------
    pd.DataFrame
        Component breakdown.
    """
    rows = [
        ("Base risk-free rate", pricing["base_rate"], "Active AU risk-free rate"),
        ("+ Funding spread", pricing["funding_spread"], "Bank cost of wholesale funding"),
        ("+ Operating / servicing spread", pricing["operating_spread"], "Admin and operational costs"),
        ("+ Capital / target return spread", pricing["capital_spread"], "Required return on capital"),
        ("+ PVEL spread", pricing["pvel_spread"], "Core expected-loss spread"),
        ("+ Credit score overlay", pricing["score_overlay"], "Scorecard-driven adjustment"),
        ("+ PD overlay", pricing["pd_overlay"], "Merton PD-driven adjustment"),
        ("+ Leverage overlay", pricing["leverage_overlay"], "Debt/EBITDA-driven adjustment"),
        ("+ Liquidity overlay", pricing["liquidity_overlay"], "Working capital quality adjustment"),
        ("+ ICR/DSCR overlay", pricing["coverage_overlay"], "Cash flow serviceability adjustment"),
        ("= Total model margin", pricing["total_margin"], "All overlays combined"),
        ("= Indicative all-in rate", pricing["all_in_rate"], pricing["comment"]),
    ]
    return pd.DataFrame(rows, columns=["Component", "Rate", "Comment"])
