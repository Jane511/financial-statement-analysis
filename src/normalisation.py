"""
Earnings Normalisation (EBITDAO)
================================
Adjusts reported earnings to reflect true operating performance by removing
non-recurring items and adjusting for owner salary — the "O" in EBITDAO.

Aligns with Commercial Ready course Steps 1-4:
  1. What are the Earnings? (EBIT)
  2. Owner Contribution (salary adjustment)
  3. Other Adjustments (one-off items)
  4. Total Available for Servicing (EBITDAO)

In the synthetic dataset, EBITDA is already provided (approximating EBITDAO).
This module demonstrates the normalisation logic that would be applied to
raw financial statements in practice.
"""

import pandas as pd
import numpy as np


def normalise_earnings(
    spread: pd.DataFrame,
    owner_salary_adjustment: float = 0.0,
    one_off_income: float = 0.0,
    one_off_expense: float = 0.0,
) -> pd.DataFrame:
    """
    Apply normalisation adjustments to derive EBITDAO from reported EBIT.

    In practice, a credit analyst would:
    - Add back: Depreciation & Amortisation, Interest, Tax
    - Adjust: Owner salary to market rate (+/- difference)
    - Remove: One-off income (e.g. government grants, asset sales)
    - Add back: One-off expenses (e.g. restructuring, legal settlements)

    Parameters
    ----------
    spread : pd.DataFrame
        Wide-format spread from financial_spreading.spread_borrower().
    owner_salary_adjustment : float
        Annual adjustment for owner salary (negative if underpaid, reducing EBITDAO).
        Example: owner takes $100k but market rate is $150k → adjustment = -50,000.
    one_off_income : float
        Non-recurring income to subtract (e.g. government grants).
    one_off_expense : float
        Non-recurring expense to add back.

    Returns
    -------
    pd.DataFrame
        Normalisation waterfall table showing EBIT → EBITDAO build-up.
    """
    periods = [c for c in spread.columns if c.startswith("FY")]

    # Extract raw values from spread
    ebit = spread.loc["ebit", periods].values.astype(float)
    interest = spread.loc["interest_expense", periods].values.astype(float)

    # D&A = EBITDA - EBIT
    ebitda = spread.loc["ebitda", periods].values.astype(float)
    depreciation = ebitda - ebit

    waterfall = pd.DataFrame(index=[
        "EBIT (reported)",
        "+ Depreciation & Amortisation",
        "+ Interest Expense",
        "= EBITDA",
        "+/- Owner Salary Adjustment (O)",
        "- One-off Income",
        "+ One-off Expense",
        "= EBITDAO (Normalised)",
    ], columns=periods)

    waterfall.loc["EBIT (reported)"] = ebit
    waterfall.loc["+ Depreciation & Amortisation"] = depreciation
    waterfall.loc["+ Interest Expense"] = interest
    waterfall.loc["= EBITDA"] = ebitda
    waterfall.loc["+/- Owner Salary Adjustment (O)"] = owner_salary_adjustment
    waterfall.loc["- One-off Income"] = -abs(one_off_income)
    waterfall.loc["+ One-off Expense"] = abs(one_off_expense)

    ebitdao = ebitda + owner_salary_adjustment - abs(one_off_income) + abs(one_off_expense)
    waterfall.loc["= EBITDAO (Normalised)"] = ebitdao

    return waterfall


def total_available_for_servicing(
    ebitdao: np.ndarray,
    interest: np.ndarray,
    scheduled_principal: np.ndarray,
) -> pd.DataFrame:
    """
    Calculate Total Available for Servicing — the surplus after debt commitments.

    This is the "first way out" test from the Commercial Ready course.

    Parameters
    ----------
    ebitdao : np.ndarray
        Normalised EBITDAO for each period.
    interest : np.ndarray
        Interest expense for each period.
    scheduled_principal : np.ndarray
        Scheduled principal repayments for each period.

    Returns
    -------
    pd.DataFrame
        Servicing waterfall.
    """
    periods = ["FY-2", "FY-1", "FY0"]
    total_repayments = interest + scheduled_principal
    surplus = ebitdao - total_repayments

    waterfall = pd.DataFrame({
        "EBITDAO": ebitdao,
        "Interest": interest,
        "Scheduled Principal": scheduled_principal,
        "Total Repayments": total_repayments,
        "Surplus / (Deficit)": surplus,
        "DSCR (EBITDAO / Repayments)": np.where(
            total_repayments > 0,
            ebitdao / total_repayments,
            np.nan,
        ),
    }, index=periods)

    return waterfall
