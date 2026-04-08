# Financial Statement Analysis — Commercial Cash Flow Lending

> **End-to-end credit analysis toolkit for Australian SME commercial lending, demonstrating the complete workflow from financial spreading to committee decision.**

This project implements the quantitative credit analysis process used by Australian banks for commercial cash flow lending to SMEs. It covers financial statement spreading, earnings normalisation, ratio analysis, working capital assessment, credit scoring, PD estimation, and risk-based pricing.

---

## How Banks Use This

In commercial lending, every borrower goes through a structured credit assessment before a facility is approved:

```
Financial Statements → Spread → Normalise → Ratios & Trends → Working Capital
→ Credit Score → PD Estimate → Pricing → Committee Paper → Approve/Decline
```

This project automates each step using Python, producing the same outputs a credit analyst would prepare manually.

---

## Project Structure

```
├── README.md
├── requirements.txt
├── data/
│   └── synthetic_sme_financials.csv       # 81 synthetic AU SME borrowers × 3 years
├── src/
│   ├── data_generation.py                 # Synthetic financial statement generator
│   ├── financial_spreading.py             # Standardise raw FS into common template
│   ├── normalisation.py                   # EBITDAO adjustments (owner salary, one-offs)
│   ├── ratio_engine.py                    # 20+ financial ratios
│   ├── trend_analysis.py                  # 3-period trend slopes and flags
│   ├── working_capital.py                 # Lecture-aligned WC quality analysis
│   ├── altman_zscore.py                   # Altman Z-score (SME proxy)
│   ├── merton_pd.py                       # Merton structural PD model
│   ├── credit_scorecard.py                # Weighted integrated scorecard
│   ├── risk_based_pricing.py              # EL-based pricing engine
│   └── commentary_generator.py            # Auto-generated credit narrative
├── notebooks/
│   ├── 01_Financial_Spreading_and_Normalisation.ipynb
│   ├── 02_Ratio_Analysis_and_Trends.ipynb
│   ├── 03_Working_Capital_Deep_Dive.ipynb
│   ├── 04_Credit_Scoring_and_PD_Estimation.ipynb
│   ├── 05_Risk_Based_Pricing.ipynb
│   └── 06_Full_Credit_Paper_Walkthrough.ipynb
├── outputs/
│   ├── figures/
│   └── tables/
└── docs/
    └── methodology.md
```

---

## The 5 C's of Credit Framework

This project primarily addresses **Capacity** and **Capital** — the quantitative pillars:

| C | What It Measures | How This Project Addresses It |
|---|-------------------|-------------------------------|
| **Character** | Willingness to repay | Credit score, ATO history (qualitative — outside model scope) |
| **Capacity** | Ability to repay from cash flow | ICR, DSCR, FCCR, FCF, EBITDAO — the "first way out" |
| **Capital** | Borrower's equity / skin in the game | Net worth trend, equity infusion, tangible net worth |
| **Collateral** | Assets pledged as security | LGD model (see Folder 2 in this repo) — the "second way out" |
| **Conditions** | Macro/industry factors, covenants | Covenant recommendations, industry benchmarking |

---

## Key Ratios Calculated

### Coverage (The "Four Measures of Capacity")
| Ratio | Formula | Bank Threshold |
|-------|---------|---------------|
| ICR | EBIT / Interest Expense | >= 2.0x |
| DSCR | OCF / (Interest + Scheduled Principal) | >= 1.20x |
| FCCR | EBITDA / (Interest + Leases + Tax + Principal) | >= 1.20x |
| Payback Ratio | (Total Debt - Cash) / EBITDA | Context-dependent |

### Leverage
| Ratio | Formula | Bank Threshold |
|-------|---------|---------------|
| Debt / EBITDA | Total Debt / EBITDA | <= 4.0x |
| Debt / Cash Flow | Total Debt / OCF | Context-dependent |
| Debt / Assets | Total Debt / Total Assets | <= 0.60 |

### Liquidity
| Ratio | Formula | Bank Threshold |
|-------|---------|---------------|
| Current Ratio | Current Assets / Current Liabilities | >= 1.20x |
| Quick Ratio | (Cash + Debtors) / Current Liabilities | >= 0.80x |
| Working Capital | Current Assets - Current Liabilities | > 0 |

### Profitability & Efficiency
| Ratio | Formula |
|-------|---------|
| EBITDA Margin | EBITDA / Revenue |
| Net Margin | NPAT / Revenue |
| ROA / ROE | NPAT / Total Assets, NPAT / Net Worth |
| Debtor Days | Debtors × 365 / Revenue |

---

## Credit Scoring & PD Models

### Integrated Scorecard
- 14 weighted metrics (Z-score, DSCR, ICR, FCCR, leverage, liquidity, Merton PD, WC quality, trends)
- Weighted score 0-1 → Internal grade: **A** (>=80%) / **B** (>=60%) / **C** (>=40%) / **D** (<40%)
- Decision: A/B → APPROVE, C → REFER, D → DECLINE

### Altman Z-Score (SME Proxy)
- Uses book equity as proxy for market capitalisation (SMEs are not listed)
- Z > 2.99 → Safe | 1.8-2.99 → Grey Zone | < 1.8 → Distress

### Merton Structural PD
- Models equity as a call option on assets
- Distance-to-Default → PD = N(-DD)
- Produces PVEL (Present Value of Expected Loss) and implied LGD

---

## Sample Output — Reference Borrower

**Example AU SME Pty Ltd** (Manufacturing, Revenue A$22.5M)

| Metric | Value | Status |
|--------|-------|--------|
| DSCR | 1.875x | PASS |
| ICR | 4.5x | PASS |
| Debt/EBITDA | 1.90x | PASS |
| Current Ratio | 1.60x | PASS |
| Z-Score | 2.885 | GREY (improving) |
| Merton PD | 5.4% | Moderate |
| Working Capital | GREEN | Cash-backed |
| **Scorecard** | **84%** | **Grade A — APPROVE** |

---

## How This Connects to the Full Credit Risk Lifecycle

```
This repo: credit-risk-portfolio_bank/
├── 1. PD Modelling (Home Loan)                    ← Retail PD scorecard
├── 2. LGD Model (Mortgage)                        ← Retail LGD
├── 8. Financial Statement Analysis (THIS PROJECT)  ← Commercial FSA + scoring
└── LGD/ (Commercial Cash Flow LGD)                ← Commercial LGD
```

Together these demonstrate the complete **PD → LGD → EAD → EL → Pricing → Monitoring** chain that underpins bank credit risk management.

---

## Getting Started

```bash
pip install -r requirements.txt
cd notebooks
jupyter notebook
```

Run notebooks in order (01 → 06). The reference borrower (borrower_id=0) matches the Excel model for verification.

---

## Technical Details

- **Python 3.10+** with pandas, numpy, scipy, matplotlib, seaborn
- **81 synthetic borrowers** across 5 ANZSIC industries × 3 annual periods
- **APRA-aligned** methodology (APS 113 / Basel III IRB concepts)
- All formulas verified against the AU SME Borrower Model Excel workbook
