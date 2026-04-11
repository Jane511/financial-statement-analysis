# Methodology - financial-statement-analysis

1. Load or generate synthetic demo data.
2. Standardise borrower, facility, exposure, collateral, and financial fields.
3. Build utilisation, margin, DSCR, leverage, liquidity, working-capital, and collateral coverage features.
4. Run the `financial` engine.
5. Validate and export CSV outputs.

## Output contract

- `outputs/tables/standardised_borrower_financials.csv`
- `outputs/tables/ratio_summary_tables.csv`
- `outputs/tables/working_capital_metrics.csv`
- `outputs/tables/trend_diagnostics.csv`
- `outputs/tables/qualitative_risk_flags.csv`
