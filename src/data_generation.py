"""
Synthetic Australian SME Financial Statement Generator
======================================================
Generates realistic 3-year financial statements (FY-2 audited, FY-1 audited, FY0 management
accounts) for Australian SME borrowers across multiple industries.

Includes a base-case borrower ("Base Case AU SME Pty Ltd") as borrower_id=0
so that downstream calculations can be checked against a stable benchmark.

Fields align with the Company_Inputs sheet of AU_SME_Borrower_Model_Final_v4_updated.xlsx.
"""

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# ANZSIC industry profiles — mean revenue, margin bands, growth, volatility
# ---------------------------------------------------------------------------
INDUSTRY_PROFILES = {
    "Manufacturing": {
        "revenue_range": (8_000_000, 50_000_000),
        "ebitda_margin": (0.08, 0.18),
        "growth_mean": 0.06,
        "growth_std": 0.08,
        "sector_sigma": 0.50,
        "expected_return": 0.0797,
    },
    "Retail Trade": {
        "revenue_range": (3_000_000, 30_000_000),
        "ebitda_margin": (0.05, 0.12),
        "growth_mean": 0.04,
        "growth_std": 0.10,
        "sector_sigma": 0.55,
        "expected_return": 0.0650,
    },
    "Professional Services": {
        "revenue_range": (2_000_000, 25_000_000),
        "ebitda_margin": (0.15, 0.30),
        "growth_mean": 0.08,
        "growth_std": 0.07,
        "sector_sigma": 0.40,
        "expected_return": 0.0900,
    },
    "Construction": {
        "revenue_range": (5_000_000, 60_000_000),
        "ebitda_margin": (0.06, 0.14),
        "growth_mean": 0.05,
        "growth_std": 0.12,
        "sector_sigma": 0.60,
        "expected_return": 0.0700,
    },
    "Health Care": {
        "revenue_range": (5_000_000, 80_000_000),
        "ebitda_margin": (0.10, 0.22),
        "growth_mean": 0.05,
        "growth_std": 0.08,
        "sector_sigma": 0.45,
        "expected_return": 0.0680,
    },
    "Transport & Logistics": {
        "revenue_range": (4_000_000, 40_000_000),
        "ebitda_margin": (0.08, 0.16),
        "growth_mean": 0.05,
        "growth_std": 0.09,
        "sector_sigma": 0.52,
        "expected_return": 0.0750,
    },
    "Wholesale Trade": {
        "revenue_range": (5_000_000, 80_000_000),
        "ebitda_margin": (0.04, 0.10),
        "growth_mean": 0.04,
        "growth_std": 0.07,
        "sector_sigma": 0.48,
        "expected_return": 0.0700,
    },
}

# ---------------------------------------------------------------------------
# Base-case borrower used for benchmark validation
# ---------------------------------------------------------------------------
REFERENCE_BORROWER = {
    "borrower_id": 0,
    "borrower_name": "Base Case AU SME Pty Ltd",
    "anzsic_division": "Manufacturing",
    "periods": ["FY-2", "FY-1", "FY0"],
    "revenue": [18_000_000, 20_000_000, 22_500_000],
    "ebitda": [2_300_000, 2_800_000, 3_150_000],
    "ebit": [1_950_000, 2_350_000, 2_700_000],
    "npat": [1_100_000, 1_350_000, 1_620_000],
    "operating_cash_flow": [1_500_000, 1_900_000, 2_250_000],
    "cash": [1_200_000, 1_500_000, 1_800_000],
    "debtors": [2_700_000, 2_900_000, 3_100_000],
    "inventory": [1_350_000, 1_450_000, 1_550_000],
    "current_assets": [5_800_000, 6_400_000, 7_200_000],
    "current_liabilities": [4_000_000, 4_200_000, 4_500_000],
    "total_assets": [12_500_000, 13_200_000, 14_000_000],
    "total_debt": [6_500_000, 6_200_000, 6_000_000],
    "interest_expense": [700_000, 650_000, 600_000],
    "share_capital": [1_200_000, 1_300_000, 1_400_000],
    "net_worth": [2_000_000, 2_800_000, 3_500_000],
    "scheduled_principal": [500_000, 550_000, 600_000],
    "capex": [400_000, 500_000, 600_000],
    "dividends": [150_000, 180_000, 200_000],
    "intangible_assets": [300_000, 280_000, 250_000],
    "lease_fixed_charges": [120_000, 130_000, 140_000],
    "tax_paid": [320_000, 380_000, 450_000],
}


def _generate_single_borrower(borrower_id: int, rng: np.random.Generator) -> list[dict]:
    """Generate 3 years of financial statements for one synthetic SME borrower."""
    industry = rng.choice(list(INDUSTRY_PROFILES.keys()))
    profile = INDUSTRY_PROFILES[industry]

    # Base revenue in FY-2
    rev_lo, rev_hi = profile["revenue_range"]
    base_revenue = rng.uniform(rev_lo, rev_hi)

    # Growth rates for FY-2→FY-1 and FY-1→FY0
    g1 = rng.normal(profile["growth_mean"], profile["growth_std"])
    g2 = rng.normal(profile["growth_mean"], profile["growth_std"])
    # Allow some negative growth but cap extreme values
    g1 = np.clip(g1, -0.20, 0.35)
    g2 = np.clip(g2, -0.20, 0.35)

    revenues = [
        base_revenue,
        base_revenue * (1 + g1),
        base_revenue * (1 + g1) * (1 + g2),
    ]

    # EBITDA margin with slight drift
    margin_lo, margin_hi = profile["ebitda_margin"]
    base_margin = rng.uniform(margin_lo, margin_hi)
    margins = [
        base_margin + rng.normal(0, 0.01),
        base_margin + rng.normal(0, 0.01),
        base_margin + rng.normal(0, 0.01),
    ]
    margins = [np.clip(m, 0.02, 0.40) for m in margins]

    ebitda = [r * m for r, m in zip(revenues, margins)]

    # D&A as 1-3% of revenue
    da_pct = rng.uniform(0.01, 0.03)
    depreciation = [r * da_pct for r in revenues]
    ebit = [eb - d for eb, d in zip(ebitda, depreciation)]

    # Interest expense: starts at 4-7% of initial debt, declines slightly
    debt_to_rev = rng.uniform(0.20, 0.45)
    initial_debt = revenues[0] * debt_to_rev
    debt_reduction = rng.uniform(0.02, 0.08)
    total_debt = [
        initial_debt,
        initial_debt * (1 - debt_reduction),
        initial_debt * (1 - debt_reduction) ** 2,
    ]

    int_rate = rng.uniform(0.06, 0.10)
    interest = [d * int_rate for d in total_debt]

    # Tax at ~25-30%
    tax_rate = rng.uniform(0.25, 0.30)
    pbt = [e - i for e, i in zip(ebit, interest)]
    npat = [max(p * (1 - tax_rate), p * 0.5) for p in pbt]
    tax_paid = [max(p * tax_rate, 0) for p in pbt]

    # Operating cash flow ≈ NPAT + D&A ± working capital movement
    ocf = [n + d + rng.normal(0, revenues[j] * 0.01) for j, (n, d) in enumerate(zip(npat, depreciation))]

    # Balance sheet items
    debtor_days = rng.uniform(30, 75)
    debtors = [r * debtor_days / 365 for r in revenues]

    inv_days = rng.uniform(20, 60) if industry != "Professional Services" else rng.uniform(0, 10)
    inventory = [r * inv_days / 365 for r in revenues]

    cash_pct = rng.uniform(0.04, 0.12)
    cash = [r * cash_pct for r in revenues]

    # Current assets = cash + debtors + inventory + other
    other_ca_pct = rng.uniform(0.01, 0.04)
    current_assets = [c + d + inv + r * other_ca_pct for c, d, inv, r in zip(cash, debtors, inventory, revenues)]

    # Current liabilities
    cl_ratio = rng.uniform(0.60, 1.10)  # CA/CL ratio target
    current_liabilities = [ca / max(cl_ratio + rng.normal(0, 0.05), 0.5) for ca in current_assets]

    # Total assets
    nca_pct = rng.uniform(0.40, 0.65)
    total_assets = [ca / (1 - nca_pct) for ca in current_assets]

    # Net worth / equity — grows with retained earnings
    base_equity = total_assets[0] * rng.uniform(0.15, 0.35)
    net_worth = [
        base_equity,
        base_equity + npat[0] * 0.6,
        base_equity + npat[0] * 0.6 + npat[1] * 0.6,
    ]

    share_capital = [nw * rng.uniform(0.30, 0.50) for nw in net_worth]

    # Capex, dividends, principal
    capex = [r * rng.uniform(0.02, 0.04) for r in revenues]
    dividends = [max(n * rng.uniform(0.10, 0.20), 0) for n in npat]
    scheduled_principal = [d * rng.uniform(0.06, 0.12) for d in total_debt]

    intangibles = [ta * rng.uniform(0.01, 0.05) for ta in total_assets]
    lease_charges = [r * rng.uniform(0.005, 0.015) for r in revenues]

    name_prefix = rng.choice([
        "Alpha", "Beta", "Delta", "Gamma", "Sigma", "Apex", "Core",
        "Pacific", "Southern", "Metro", "Coastal", "Highland", "Urban",
        "Swift", "Peak", "Atlas", "Nova", "Titan", "Vanguard", "Zenith",
    ])
    name_suffix = rng.choice([
        "Industries", "Group", "Holdings", "Solutions", "Services",
        "Engineering", "Trading", "Logistics", "Corp", "Enterprises",
    ])
    borrower_name = f"{name_prefix} {name_suffix} Pty Ltd"

    periods = ["FY-2", "FY-1", "FY0"]
    rows = []
    for j, period in enumerate(periods):
        rows.append({
            "borrower_id": borrower_id,
            "borrower_name": borrower_name,
            "anzsic_division": industry,
            "period": period,
            "revenue": round(revenues[j]),
            "ebitda": round(ebitda[j]),
            "ebit": round(ebit[j]),
            "npat": round(npat[j]),
            "operating_cash_flow": round(ocf[j]),
            "cash": round(cash[j]),
            "debtors": round(debtors[j]),
            "inventory": round(inventory[j]),
            "current_assets": round(current_assets[j]),
            "current_liabilities": round(current_liabilities[j]),
            "total_assets": round(total_assets[j]),
            "total_debt": round(total_debt[j]),
            "interest_expense": round(interest[j]),
            "share_capital": round(share_capital[j]),
            "net_worth": round(net_worth[j]),
            "scheduled_principal": round(scheduled_principal[j]),
            "capex": round(capex[j]),
            "dividends": round(dividends[j]),
            "intangible_assets": round(intangibles[j]),
            "lease_fixed_charges": round(lease_charges[j]),
            "tax_paid": round(tax_paid[j]),
        })
    return rows


def _reference_borrower_rows() -> list[dict]:
    """Return the benchmark borrower as 3 rows."""
    ref = REFERENCE_BORROWER
    rows = []
    for j, period in enumerate(ref["periods"]):
        row = {
            "borrower_id": ref["borrower_id"],
            "borrower_name": ref["borrower_name"],
            "anzsic_division": ref["anzsic_division"],
            "period": period,
        }
        for field in [
            "revenue", "ebitda", "ebit", "npat", "operating_cash_flow",
            "cash", "debtors", "inventory", "current_assets", "current_liabilities",
            "total_assets", "total_debt", "interest_expense", "share_capital",
            "net_worth", "scheduled_principal", "capex", "dividends",
            "intangible_assets", "lease_fixed_charges", "tax_paid",
        ]:
            row[field] = ref[field][j]
        rows.append(row)
    return rows


def generate_sme_dataset(n_borrowers: int = 80, seed: int = 42) -> pd.DataFrame:
    """
    Generate a dataset of synthetic AU SME borrowers.

    Parameters
    ----------
    n_borrowers : int
        Number of synthetic borrowers to generate (in addition to the benchmark borrower).
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame with one row per borrower-period (3 rows per borrower).
        Columns match the Company_Inputs sheet fields.
    """
    rng = np.random.default_rng(seed)
    all_rows = _reference_borrower_rows()

    for i in range(1, n_borrowers + 1):
        all_rows.extend(_generate_single_borrower(i, rng))

    df = pd.DataFrame(all_rows)

    # Ensure consistent column order
    col_order = [
        "borrower_id", "borrower_name", "anzsic_division", "period",
        "revenue", "ebitda", "ebit", "npat", "operating_cash_flow",
        "cash", "debtors", "inventory", "current_assets", "current_liabilities",
        "total_assets", "total_debt", "interest_expense", "share_capital",
        "net_worth", "scheduled_principal", "capex", "dividends",
        "intangible_assets", "lease_fixed_charges", "tax_paid",
    ]
    return df[col_order]


if __name__ == "__main__":
    df = generate_sme_dataset(n_borrowers=80)
    print(f"Generated {df['borrower_id'].nunique()} borrowers, {len(df)} rows")
    print(df.head(6))
    out_path = "data/synthetic_sme_financials.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved to {out_path}")
