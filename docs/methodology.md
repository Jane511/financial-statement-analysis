# Methodology — Financial Statement Analysis for Commercial Cash Flow Lending

## Overview

This document maps each analysis module to its source methodology: the Commercial Ready professional course, the AU SME Borrower Model (Excel), and standard Australian bank credit practice.

---

## 1. Financial Spreading (`financial_spreading.py`)

**Source:** Standard bank practice — every major AU bank uses a spreading template.

**Process:**
- Raw financial statements (Income Statement, Balance Sheet, Cash Flow Statement) are organised into a standardised side-by-side format
- Periods: FY-2 (audited), FY-1 (audited), FY0 (management accounts)
- Maps to `Company_Inputs` sheet in the Excel model

Consistency enables ratio calculation, peer comparison, and trend analysis across the portfolio.

---

## 2. Earnings Normalisation (`normalisation.py`)

**Source:** Commercial Ready course Steps 1-4.

**EBITDAO build-up:**
```
EBIT (reported Operating Profit)
+ Depreciation & Amortisation
+ Interest Expense
= EBITDA
+/- Owner Salary Adjustment (the "O" in EBITDAO)
- One-off Income (e.g. government grants, asset sale gains)
+ One-off Expenses (e.g. restructuring, legal settlements)
= EBITDAO (Normalised)
```

**Key concept:** The owner salary adjustment is critical for SMEs. If the owner takes $100k but market replacement cost is $150k, EBITDAO must be reduced by $50k to reflect the true cost of running the business.

---

## 3. Ratio Engine (`ratio_engine.py`)

**Source:** Derived_Ratios sheet + Commercial Ready "Four Measures of Capacity".

### Coverage Ratios (The "First Way Out")

| Ratio | Formula | Threshold | Course Reference |
|-------|---------|-----------|------------------|
| ICR | EBIT / Interest Expense | >= 2.0x | Commercial Ready: "EBITO / Total Interest = 5.35 times" |
| DSCR | OCF / (Interest + Scheduled Principal) | >= 1.20x | Commercial Ready: "EBITDAO / Total Repayment Obligations = 2.42" |
| FCCR | EBITDA / (Interest + Leases + Tax + Principal) | >= 1.20x | Excel model: IC_Decision row 32 |
| Payback | (Total Debt - Cash) / EBITDA | Context | Commercial Ready: "Total Proposed Debt - Cash / Total EBITDAO" |

### Verification (Reference Borrower FY0)
- ICR: 2,700,000 / 600,000 = **4.5x** ✓
- DSCR: 2,250,000 / (600,000 + 600,000) = **1.875x** ✓
- Debt/EBITDA: 6,000,000 / 3,150,000 = **1.905x** ✓
- Current Ratio: 7,200,000 / 4,500,000 = **1.60x** ✓
- Quick Ratio: (1,800,000 + 3,100,000) / 4,500,000 = **1.089x** ✓

---

## 4. Trend Analysis (`trend_analysis.py`)

**Source:** Derived_Ratios sheet rows 23-40.

**Method:**
- Linear slope across 3 equally-spaced periods (FY-2, FY-1, FY0)
- Classification: POSITIVE (improving), NEGATIVE (deteriorating), FLAT
- For inverse metrics (e.g. Debt/EBITDA), a negative slope = POSITIVE
- Automated narrative comments generated for each metric

**Why 3 periods:** Banks require minimum 2 audited years + current management accounts. One period can be an anomaly; three periods show a trend.

---

## 5. Working Capital Analysis (`working_capital.py`)

**Source:** Working_Capital_Analysis sheet.

**Lecture flow:**
1. Remove cash from current assets → CA excl cash
2. Test raw WC gap: CA excl cash - Current Liabilities
3. Add cash back → Final WC (true short-term liquidity)
4. Test if borrowing is needed to make WC positive
5. Analyse composition: cash share, debtor share, inventory share
6. Determine if debt is funding WC deficits vs growth/expansion

**Flag logic:**
- GREEN: Final WC positive AND raw WC (excl cash) positive
- AMBER: Final WC positive BUT raw WC negative (cash covers gap)
- RED: Final WC negative (borrowing needed for short-term liquidity)

**Verification:** Reference borrower: Raw WC excl cash = 5,400,000 - 4,500,000 = 900,000 > 0 → **GREEN** ✓

---

## 6. Altman Z-Score (`altman_zscore.py`)

**Source:** Sigma_Final sheet.

**Formula (original Altman 1968 with book equity proxy):**
```
Z = 1.2*T1 + 1.4*T2 + 3.3*T3 + 0.6*T4 + 1.0*T5

T1 = Working Capital / Total Assets
T2 = Retained Earnings / Total Assets (proxy: Net Worth - Share Capital)
T3 = EBIT / Total Assets
T4 = Book Equity / Total Liabilities (proxy for Market Cap / TL)
T5 = Revenue / Total Assets
```

**Zones:** Safe (>2.99) | Grey (1.8-2.99) | Distress (<1.8)

**Verification (FY0):**
- T1 = 2,700,000 / 14,000,000 = 0.1929
- T2 = (3,500,000 - 1,400,000) / 14,000,000 = 0.1500
- T3 = 2,700,000 / 14,000,000 = 0.1929
- T4 = 3,500,000 / 10,500,000 = 0.3333
- T5 = 22,500,000 / 14,000,000 = 1.6071
- Z = 1.2(0.1929) + 1.4(0.1500) + 3.3(0.1929) + 0.6(0.3333) + 1.0(1.6071) = **2.885** ✓

---

## 7. Merton Structural PD (`merton_pd.py`)

**Source:** Merton_PD_EL sheet.

**Model:**
- Asset value A = Total Assets (proxy for SME — no market cap available)
- Debt barrier D = Total Debt
- Volatility σ = max(industry sector sigma, observed annual sigma)
- Expected return μ = industry proxy (from ANZSIC mapping)

**Distance-to-Default:**
```
DD = [ln(A/D) + (μ - σ²/2) * T] / (σ * √T)
PD = N(-DD)
```

**PVEL (Present Value of Expected Loss):**
```
Discounted Default Leg = D * exp(-r*T) * PD
Recovery Leg = A * N(-E1)   where E1 = DD + σ√T
PVEL = Discounted Default Leg - Recovery Leg
Implied LGD = PVEL / Discounted Default Leg
```

---

## 8. Credit Scorecard (`credit_scorecard.py`)

**Source:** IC_Decision sheet (Institutional Internal Rating Scorecard).

**14 weighted metrics:**

| Metric | Rule | Weight |
|--------|------|--------|
| Z-score FY0 | >= 1.8 | 6% |
| Z-score trend | UP or FLAT | 3% |
| Debt / EBITDA | <= 4.0x | 7% |
| DSCR | >= 1.20x | 9% |
| ICR | >= 2.0x | 7% |
| FCCR | >= 1.20x | 7% |
| Current Ratio | >= 1.20x | 4% |
| Quick Ratio | >= 0.80x | 4% |
| Free Cash Flow | > 0 | 9% |
| Tangible Net Worth | > 0 | 7% |
| Merton PD | <= 10% | 7% |
| Working Capital Flag | not RED | 5% |
| Selected Sigma | <= 50% | 3% |
| Core Trend Flags | >= 7 of 8 | 6% |

**Grading:** A (>=80%) → APPROVE | B (>=60%) → APPROVE | C (>=40%) → REFER | D (<40%) → DECLINE

---

## 9. Risk-Based Pricing (`risk_based_pricing.py`)

**Rate build-up:**
```
Base rate (risk-free / BBSY proxy)
+ Funding spread (wholesale funding cost)
+ Operating spread (admin/servicing)
+ Capital spread (ROE hurdle)
+ PVEL spread (expected loss)
+ Credit score overlay
+ PD overlay
+ Leverage overlay
+ Liquidity overlay
+ ICR/DSCR overlay
= Indicative all-in rate
```

---

## 10. Commentary Generator (`commentary_generator.py`)

**Source:** Automated_Comments sheet.

Generates structured credit committee narratives covering:
1. Borrower overview
2. Financial trends
3. Working capital assessment
4. Repayment capacity
5. Credit quality (Z-score, Merton PD)
6. Scorecard and pricing
7. Recommended covenants

**Bank use:** Reduces time to prepare credit papers and ensures consistent coverage of all required assessment areas.
