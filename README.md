# Commercial Financial Statement Analysis Project

This repository is the borrower financial analysis layer at the front of the public commercial credit-risk stack. It uses synthetic borrower statements and benchmark-style reference data to produce standardised financials, ratio summaries, working-capital metrics, and qualitative risk flags that can support both structured credit assessment and practical lending decisioning workflows.

## What this repo is

This project demonstrates how borrower financial information can be turned into reusable commercial credit-analysis outputs. It is designed for recruiter and employer review, so the repo emphasises clear structure, explainable metrics, and portfolio-style documentation across both bank-style credit review and non-bank underwriting use cases.

## Where it sits in the stack

Upstream inputs:
- synthetic borrower statements and benchmark reference data staged under `data/`

Downstream consumers:
- `PD-and-scorecard-commercial`
- `LGD-commercial`

## How this is used in practice

This project can be applied in:

### Bank / Institutional context

- Borrower financial spreading and ratio review for structured credit assessment
- Serviceability, leverage, and working-capital analysis for portfolio risk review
- Consistent financial inputs for downstream PD, LGD, and monitoring workflows

### Non-bank / Fintech context

- Financial analysis inputs for originations decisioning and approval strategy
- Cash-flow and liquidity review for lender-side underwriting
- Early borrower quality diagnostics for portfolio performance tracking

## Key inputs

- synthetic borrower financial statements
- public listed-company style benchmark extracts
- financial spreading, ratio, and qualitative assessment assumptions staged under `data/`

## Key outputs

- `outputs/tables/standardised_borrower_financials.csv`
- `outputs/tables/ratio_summary_tables.csv`
- `outputs/tables/working_capital_metrics.csv`
- `outputs/tables/trend_diagnostics.csv`
- `outputs/tables/qualitative_risk_flags.csv`
- `outputs/tables/pipeline_validation_report.csv`

## Repo structure

- `data/`: raw, interim, processed, and external borrower-analysis inputs
- `reports/`: retained PDF artifacts (`reports/public_company_analysis/` and `reports/portfolio_overview.pdf`) for reviewer-facing examples
- `src/`: reusable financial spreading, ratio, and pipeline modules
- `scripts/`: wrapper scripts for pipeline execution
- `docs/`: methodology, assumptions, data dictionary, and validation notes
- `notebooks/`: walkthrough notebooks for reviewer context
- `outputs/`: exported tables, reports, and sample artifacts
- `tests/`: validation and regression checks

Compatibility note:
- Older setups that still contain a top-level `Reports/` folder are automatically migrated to the canonical `reports/` layout by `src/public_company_analysis.py`.

## How to run

```powershell
python -m src.codex_run_pipeline
```

Or:

```powershell
python scripts/run_codex_pipeline.py
```

## Limitations / Demo-Only Note

- All borrower records are synthetic and are included for demonstration only.
- Benchmarking and qualitative flags use simplified portfolio assumptions rather than internal bank financial spreading rules.
- The repo is intended to show reusable analytical workflow and reporting quality, not to represent a production credit spreading platform.
