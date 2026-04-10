from pathlib import Path
PROJECT_ROOT=Path(__file__).resolve().parents[1]
REPO_NAME='Financial-Statement-Analysis'
PIPELINE_KIND='financial'
EXPECTED_OUTPUTS=['standardised_borrower_financials.csv', 'ratio_summary_tables.csv', 'working_capital_metrics.csv', 'trend_diagnostics.csv', 'qualitative_risk_flags.csv']
