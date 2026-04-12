# Commercial Borrower Financial Statement Analysis Project

This repository is the borrower financial analysis layer at the front of the public commercial credit-risk stack. It uses synthetic borrower statements and benchmark-style reference data to produce standardised financials, ratio summaries, working-capital metrics, and qualitative risk flags for downstream scoring, loss, pricing, and monitoring workflows.

## What this repo is

This project demonstrates how borrower financial information can be turned into reusable commercial credit-analysis outputs. It is designed for recruiter and employer review, so the repo emphasises clear structure, explainable metrics, and portfolio-style documentation rather than raw modelling complexity.

## Where it sits in the stack

This repo sits at the front of the public commercial stack and feeds downstream borrower scoring, LGD interpretation, pricing analysis, and portfolio monitoring.

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
- `Reports/`: retained PDF credit reports for reviewer-facing examples from the public-company analysis workflow
- `src/`: reusable financial spreading, ratio, and pipeline modules
- `scripts/`: wrapper scripts for pipeline execution
- `docs/`: methodology, assumptions, data dictionary, and validation notes
- `notebooks/`: walkthrough notebooks for reviewer context
- `outputs/`: exported tables, reports, and sample artifacts
- `tests/`: validation and regression checks

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
