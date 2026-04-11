# Data Dictionary - financial-statement-analysis

| Field | Description |
| --- | --- |
| `borrower_id` | Synthetic borrower identifier. |
| `facility_id` | Synthetic facility identifier. |
| `segment` | Portfolio segment. |
| `industry` | Australian industry grouping. |
| `product_type` | Facility or product type. |
| `limit` | Approved or committed exposure limit. |
| `drawn` | Current drawn balance. |
| `pd` | Demonstration PD input. |
| `lgd` | Demonstration LGD input. |
| `ead` | Demonstration EAD input. |

## Output files

- `outputs/tables/standardised_borrower_financials.csv`
- `outputs/tables/ratio_summary_tables.csv`
- `outputs/tables/working_capital_metrics.csv`
- `outputs/tables/trend_diagnostics.csv`
- `outputs/tables/qualitative_risk_flags.csv`
