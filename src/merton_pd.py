"""
Merton Structural PD Model
============================
Estimates Probability of Default using the Merton (1974) structural model.
Maps to the Merton_PD_EL sheet of the AU SME Borrower Model.

The model treats the firm's equity as a call option on its assets:
  - Asset value (A) = Total Assets (proxy for SME)
  - Debt threshold (D) = Total Debt (default barrier)
  - Expected return (μ) = industry proxy or borrower growth
  - Volatility (σ) = sector sigma (from Sigma_Final sheet)
  - Time horizon (T) = 1 year
  - Risk-free rate (r) = RBA cash rate proxy

Distance-to-Default:
  DD = [ln(A/D) + (μ - σ²/2)*T] / (σ * √T)

Probability of Default:
  PD = N(-DD)    where N() is the standard normal CDF

Present Value of Expected Loss (PVEL):
  PVEL = D*exp(-r*T)*PD*N(-E1)/N(-DD) - A*N(-E1)
  Simplified: PVEL = Discounted_Default_Leg - Recovery_Leg

Verification: Reference borrower should produce PD ≈ 5.36%, PVEL ≈ $62,578
"""

import numpy as np
from scipy.stats import norm
import pandas as pd

from .data_generation import INDUSTRY_PROFILES


def get_sector_sigma(anzsic_division: str) -> float:
    """Look up sector proxy sigma from industry profiles."""
    profile = INDUSTRY_PROFILES.get(anzsic_division)
    if profile:
        return profile["sector_sigma"]
    return 0.50  # default


def get_expected_return(anzsic_division: str) -> float:
    """Look up industry expected return proxy."""
    profile = INDUSTRY_PROFILES.get(anzsic_division)
    if profile:
        return profile["expected_return"]
    return 0.075  # default


def compute_merton_pd(
    total_assets: float,
    total_debt: float,
    sigma: float,
    mu: float,
    rf: float = 0.0464,
    T: float = 1.0,
) -> dict:
    """
    Compute Merton PD and PVEL for a single borrower.

    Parameters
    ----------
    total_assets : float
        Asset value proxy (A).
    total_debt : float
        Debt threshold / default barrier (D).
    sigma : float
        Asset volatility (σ).
    mu : float
        Expected asset return (μ).
    rf : float
        Risk-free rate. Default 4.64% (AU proxy).
    T : float
        Time horizon in years.

    Returns
    -------
    dict
        PD, PVEL, distance-to-default, implied LGD, and supporting metrics.
    """
    A = total_assets
    D = total_debt

    if A <= 0 or D <= 0 or sigma <= 0:
        return {
            "asset_value": A, "debt_threshold": D, "sigma": sigma, "mu": mu,
            "rf": rf, "T": T, "dd": np.nan, "pd": np.nan, "pvel": np.nan,
            "implied_lgd": np.nan, "leverage_comment": "Insufficient data",
            "pd_comment": "Insufficient data",
        }

    sqrt_T = np.sqrt(T)

    # Distance-to-default (E2 in the Excel model)
    dd = (np.log(A / D) + (mu - 0.5 * sigma**2) * T) / (sigma * sqrt_T)

    # E1 term
    e1 = dd + sigma * sqrt_T

    # PD = N(-dd)
    pd_value = norm.cdf(-dd)

    # PVEL calculation
    discounted_debt = D * np.exp(-rf * T)
    discounted_default_leg = discounted_debt * pd_value
    recovery_leg = A * norm.cdf(-e1)
    pvel = discounted_default_leg - recovery_leg

    # Implied LGD
    implied_lgd = pvel / discounted_default_leg if discounted_default_leg > 0 else 0

    # Standard EL cross-check
    standard_el = pd_value * implied_lgd * discounted_debt

    # Narrative comments
    leverage_ratio = D / A
    if leverage_ratio < 0.3:
        leverage_comment = "Low debt load"
    elif leverage_ratio < 0.5:
        leverage_comment = "Moderate debt load"
    else:
        leverage_comment = "High debt load"

    if pd_value < 0.01:
        pd_comment = "Very low PD"
    elif pd_value < 0.05:
        pd_comment = "Low PD"
    elif pd_value < 0.10:
        pd_comment = "Moderate PD"
    elif pd_value < 0.20:
        pd_comment = "Elevated PD"
    else:
        pd_comment = "High PD"

    if pvel < 10_000:
        pvel_comment = "Low PVEL"
    elif pvel < 100_000:
        pvel_comment = "Moderate PVEL"
    else:
        pvel_comment = "High PVEL"

    return {
        "asset_value": A,
        "debt_threshold": D,
        "sigma": sigma,
        "mu": mu,
        "rf": rf,
        "T": T,
        "dd": dd,
        "e1": e1,
        "pd": pd_value,
        "discounted_default_leg": discounted_default_leg,
        "recovery_leg": recovery_leg,
        "pvel": pvel,
        "implied_lgd": implied_lgd,
        "standard_el": standard_el,
        "leverage_comment": leverage_comment,
        "pd_comment": pd_comment,
        "pvel_comment": pvel_comment,
    }


def borrower_merton_analysis(
    df: pd.DataFrame,
    borrower_id: int,
    rf: float = 0.0464,
) -> dict:
    """
    Run Merton PD for a single borrower using FY0 data.

    Parameters
    ----------
    df : pd.DataFrame
        Full dataset (long format).
    borrower_id : int
        Borrower to analyse.
    rf : float
        Risk-free rate.

    Returns
    -------
    dict
        Full Merton output.
    """
    fy0 = df[(df["borrower_id"] == borrower_id) & (df["period"] == "FY0")]
    if fy0.empty:
        return {}

    row = fy0.iloc[0]
    industry = row["anzsic_division"]
    sigma = get_sector_sigma(industry)
    mu = get_expected_return(industry)

    return compute_merton_pd(
        total_assets=row["total_assets"],
        total_debt=row["total_debt"],
        sigma=sigma,
        mu=mu,
        rf=rf,
    )


def portfolio_merton_summary(df: pd.DataFrame, rf: float = 0.0464) -> pd.DataFrame:
    """
    Compute Merton PD for all borrowers (FY0).

    Returns
    -------
    pd.DataFrame
        One row per borrower with PD, PVEL, implied LGD.
    """
    fy0 = df[df["period"] == "FY0"].copy()
    results = []
    for _, row in fy0.iterrows():
        industry = row["anzsic_division"]
        sigma = get_sector_sigma(industry)
        mu = get_expected_return(industry)
        m = compute_merton_pd(row["total_assets"], row["total_debt"], sigma, mu, rf)
        results.append({
            "borrower_id": row["borrower_id"],
            "borrower_name": row["borrower_name"],
            "anzsic_division": industry,
            "pd": m["pd"],
            "pvel": m["pvel"],
            "implied_lgd": m["implied_lgd"],
            "dd": m["dd"],
            "pd_comment": m["pd_comment"],
        })
    return pd.DataFrame(results)
