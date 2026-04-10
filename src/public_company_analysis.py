"""
Public Listed Company Analysis Runner
=====================================
Runs the existing credit-analysis toolkit across a curated two-year dataset built
from ASX-listed company annual reports and writes tables plus bank-style reports
to the outputs directory.
"""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import re
from textwrap import wrap

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / "outputs" / ".mplconfig"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd

from .altman_zscore import borrower_zscore_trend
from .commentary_generator import (
    generate_automated_comments_table,
    generate_borrower_commentary,
)
from .credit_scorecard import score_borrower
from .financial_spreading import spread_borrower
from .merton_pd import borrower_merton_analysis
from .ratio_engine import BANK_THRESHOLDS, borrower_ratio_summary, calculate_ratios
from .risk_based_pricing import compute_pricing, pricing_waterfall_table
from .trend_analysis import analyse_trends
from .working_capital import analyse_working_capital


BASE_DIR = PROJECT_ROOT
INPUT_PATH = BASE_DIR / "data" / "public_listed_company_financials.csv"
SOURCE_PATH = BASE_DIR / "data" / "public_listed_company_sources.csv"
TABLE_DIR = BASE_DIR / "outputs" / "tables" / "public_company_analysis"
REPORT_DIR = BASE_DIR / "outputs" / "reports" / "public_company_analysis"
PDF_DIR = BASE_DIR / "Reports"
ROOT_PDF_DIR = BASE_DIR
MPL_CONFIG_DIR = BASE_DIR / "outputs" / ".mplconfig"

_CASHFLOW_LENDING_INDUSTRY_MAP = {
    "Construction": "Construction - Trade Services",
    "Health Care": "Health Care and Social Assistance",
    "Retail Trade": "Retail Trade",
    "Transport & Logistics": "Transport, Postal and Warehousing",
    "Wholesale Trade": "Wholesale Trade",
}


def slugify(value: str) -> str:
    """Create a stable filename fragment from a company name."""
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def fmt_money(value: float) -> str:
    """Format a dollar value in millions for the reports."""
    if pd.isna(value):
        return "n.a."
    return f"A${value / 1_000_000:,.1f}m"


def fmt_pct(value: float) -> str:
    """Format a proportion as a percentage."""
    if pd.isna(value):
        return "n.a."
    return f"{value:.1%}"


def fmt_multiple(value: float) -> str:
    """Format a leverage or coverage multiple."""
    if pd.isna(value):
        return "n.a."
    return f"{value:,.2f}x"


def join_readable(items: list[str]) -> str:
    """Join a list of strings into a human-readable sentence fragment."""
    cleaned = [item for item in items if item]
    if not cleaned:
        return "none"
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def metric_strength(value: float, threshold: float, direction: str) -> str:
    """Classify a metric result against a simple credit guide."""
    if pd.isna(value):
        return "Unavailable"

    if direction == ">=":
        if value >= threshold * 1.5:
            return "Strong"
        if value >= threshold:
            return "Acceptable"
        if value >= threshold * 0.8:
            return "Watch"
        return "Weak"

    if direction == "<=":
        if value <= threshold * 0.75:
            return "Strong"
        if value <= threshold:
            return "Acceptable"
        if value <= threshold * 1.25:
            return "Watch"
        return "Weak"

    if direction == ">":
        return "Strong" if value > threshold else "Weak"

    if direction == "<":
        return "Strong" if value < threshold else "Weak"

    return "Informational"


def pd_risk_band(pd_value: float) -> str:
    """Bucket modelled PD for plain-English reporting."""
    if pd.isna(pd_value):
        return "unknown"
    if pd_value <= 0.01:
        return "low"
    if pd_value <= 0.05:
        return "moderate"
    return "elevated"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a simple markdown table without external dependencies."""
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def rename_period_columns(df: pd.DataFrame, year_map: dict[str, int]) -> pd.DataFrame:
    """Rename FY labels to the actual fiscal years for presentation."""
    rename_map = {
        period: f"FY{year}"
        for period, year in year_map.items()
        if period in df.columns
    }
    return df.rename(columns=rename_map)


def ensure_output_dirs() -> None:
    """Create output folders if they do not already exist."""
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    for lock_file in MPL_CONFIG_DIR.glob("*.matplotlib-lock"):
        try:
            lock_file.unlink()
        except PermissionError:
            pass


def build_cashflow_lending_public_benchmark_exports(
    df_with_ratios: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Export listed-company data in the schema expected by the PD scorecard repo."""
    export_df = df_with_ratios.copy()
    export_df["industry"] = export_df["anzsic_division"].map(_CASHFLOW_LENDING_INDUSTRY_MAP)
    export_df["source_file"] = export_df["borrower_name"].map(slugify) + "_public_company_analysis.csv"

    standard_df = (
        export_df[
            [
                "source_file",
                "borrower_name",
                "industry",
                "period",
                "revenue",
                "ebitda",
                "ebit",
                "operating_cash_flow",
                "current_assets",
                "current_liabilities",
                "total_debt",
                "interest_expense",
                "cash",
                "debtors",
                "inventory",
                "net_worth",
            ]
        ]
        .rename(columns={"borrower_name": "company_name"})
        .dropna(subset=["industry", "revenue"])
        .sort_values(["industry", "company_name", "period"])
        .reset_index(drop=True)
    )

    benchmark_df = (
        export_df.dropna(subset=["industry", "revenue"])
        .groupby("industry", as_index=False)
        .agg(
            listed_company_count=("borrower_name", "nunique"),
            listed_revenue_median=("revenue", "median"),
            listed_ebitda_margin_median=("ebitda_margin", "median"),
            listed_ocf_margin_median=("ocf_margin", "median"),
            listed_current_ratio_median=("current_ratio", "median"),
            listed_debt_to_ebitda_median=("debt_to_ebitda", "median"),
        )
        .sort_values("industry")
        .reset_index(drop=True)
    )
    benchmark_df["listed_benchmark_source"] = "Financial Statement Analysis public company outputs"
    return standard_df, benchmark_df


def build_cashflow_lending_transaction_benchmarks(
    df_with_ratios: pd.DataFrame,
    summary_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build conduct benchmark proxies for the downstream PD project."""
    latest_df = df_with_ratios[df_with_ratios["period"] == "FY0"].copy()
    previous_df = (
        df_with_ratios[df_with_ratios["period"] == "FY-1"][["borrower_name", "revenue", "ocf_margin"]]
        .rename(columns={"revenue": "revenue_fy_minus_1", "ocf_margin": "ocf_margin_fy_minus_1"})
    )
    latest_df = latest_df.merge(previous_df, on="borrower_name", how="left")
    latest_df = latest_df.merge(
        summary_df[["borrower_name", "merton_pd_fy0"]],
        on="borrower_name",
        how="left",
    )
    latest_df["industry"] = latest_df["anzsic_division"].map(_CASHFLOW_LENDING_INDUSTRY_MAP)
    latest_df = latest_df.dropna(subset=["industry"]).copy()

    revenue_growth = (
        latest_df["revenue"] / latest_df["revenue_fy_minus_1"].replace(0, pd.NA) - 1.0
    ).fillna(0.0)
    ocf_margin_delta = (latest_df["ocf_margin"] - latest_df["ocf_margin_fy_minus_1"]).fillna(0.0).abs()
    merton_pd = latest_df["merton_pd_fy0"].fillna(0.0)

    latest_df["tx_avg_monthly_credits"] = latest_df["revenue"] / 12.0
    latest_df["tx_avg_monthly_debits"] = (latest_df["revenue"] - latest_df["operating_cash_flow"]).clip(lower=0.0) / 12.0
    latest_df["tx_credit_turnover_cv"] = np.clip(
        0.04 + revenue_growth.abs() * 0.75 + ocf_margin_delta * 2.5 + merton_pd * 1.5,
        0.03,
        0.30,
    )
    latest_df["tx_months_negative_net_cash"] = np.clip(
        np.round(
            0.5
            + np.maximum(0.03 - latest_df["ocf_margin"].fillna(0.0), 0.0) * 80
            + latest_df["tx_credit_turnover_cv"] * 12
            + merton_pd * 30
        ),
        0,
        8,
    )
    latest_df["tx_failed_event_rate"] = np.clip(
        0.002
        + np.maximum(1.15 - latest_df["current_ratio"].fillna(1.15), 0.0) * 0.05
        + np.maximum(1.25 - latest_df["dscr"].fillna(1.25), 0.0) * 0.04
        + merton_pd * 0.60,
        0.0,
        0.20,
    )
    latest_df["tx_cash_advance_rate"] = np.clip(
        0.005
        + np.maximum(0.04 - latest_df["ocf_margin"].fillna(0.04), 0.0) * 0.80
        + np.maximum(1.10 - latest_df["current_ratio"].fillna(1.10), 0.0) * 0.03,
        0.0,
        0.15,
    )

    benchmark_df = (
        latest_df.groupby("industry", as_index=False)
        .agg(
            transaction_account_count=("borrower_name", "nunique"),
            tx_avg_monthly_credits_median=("tx_avg_monthly_credits", "median"),
            tx_avg_monthly_debits_median=("tx_avg_monthly_debits", "median"),
            tx_credit_turnover_cv_median=("tx_credit_turnover_cv", "median"),
            tx_months_negative_net_cash_median=("tx_months_negative_net_cash", "median"),
            tx_failed_event_rate_median=("tx_failed_event_rate", "median"),
            tx_cash_advance_rate_median=("tx_cash_advance_rate", "median"),
        )
        .sort_values("industry")
        .reset_index(drop=True)
    )
    benchmark_df["transaction_record_count"] = benchmark_df["transaction_account_count"] * 12
    benchmark_df["transaction_benchmark_source"] = "Financial Statement Analysis public company proxy conduct benchmarks"
    return benchmark_df[
        [
            "industry",
            "transaction_account_count",
            "transaction_record_count",
            "tx_avg_monthly_credits_median",
            "tx_avg_monthly_debits_median",
            "tx_credit_turnover_cv_median",
            "tx_months_negative_net_cash_median",
            "tx_failed_event_rate_median",
            "tx_cash_advance_rate_median",
            "transaction_benchmark_source",
        ]
    ]


def build_cashflow_lending_invoice_benchmarks(
    df_with_ratios: pd.DataFrame,
    summary_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build receivables benchmark proxies for the downstream PD project."""
    latest_df = df_with_ratios[df_with_ratios["period"] == "FY0"].copy()
    latest_df = latest_df.merge(
        summary_df[["borrower_name", "merton_pd_fy0"]],
        on="borrower_name",
        how="left",
    )
    latest_df["industry"] = latest_df["anzsic_division"].map(_CASHFLOW_LENDING_INDUSTRY_MAP)
    latest_df = latest_df.dropna(subset=["industry"]).copy()

    debtor_days = latest_df["debtor_days"].fillna(30.0)
    ocf_margin = latest_df["ocf_margin"].fillna(0.05)
    current_ratio = latest_df["current_ratio"].fillna(1.10)
    inventory_days = latest_df["inventory_days"].fillna(0.0)
    merton_pd = latest_df["merton_pd_fy0"].fillna(0.0)

    latest_df["invoice_top_customer_concentration_pct"] = np.clip(
        0.12 + np.minimum(debtor_days / 365.0, 0.30) * 0.60 + np.maximum(0.03 - ocf_margin, 0.0) * 1.20 + merton_pd * 0.80,
        0.10,
        0.75,
    )
    latest_df["invoice_customer_count"] = np.clip(
        np.round(6.0 / latest_df["invoice_top_customer_concentration_pct"]),
        3,
        80,
    )
    latest_df["invoice_amount_median"] = (
        latest_df["revenue"] / 12.0 / latest_df["invoice_customer_count"].replace(0, pd.NA) * 0.80
    ).fillna(0.0)
    latest_df["invoice_payment_delay_median_days"] = np.clip(debtor_days - 30.0, 0.0, 75.0)
    latest_df["invoice_late_payment_rate"] = np.clip(
        0.08
        + latest_df["invoice_payment_delay_median_days"] / 180.0
        + np.maximum(1.10 - current_ratio, 0.0) * 0.10
        + merton_pd * 0.80,
        0.02,
        0.65,
    )
    latest_df["invoice_severe_late_rate_90dpd"] = np.clip(
        0.01 + np.maximum(latest_df["invoice_payment_delay_median_days"] - 45.0, 0.0) / 300.0 + merton_pd * 0.20,
        0.0,
        0.25,
    )
    latest_df["invoice_dilution_proxy_rate"] = np.clip(
        0.01 + inventory_days / 365.0 * 0.08 + np.maximum(0.04 - ocf_margin, 0.0) * 0.60,
        0.0,
        0.20,
    )
    latest_df["invoice_record_count"] = np.clip(np.round(latest_df["invoice_customer_count"] * 12), 24, 960)

    benchmark_df = (
        latest_df.groupby("industry", as_index=False)
        .agg(
            invoice_record_count=("invoice_record_count", "median"),
            invoice_customer_count=("invoice_customer_count", "median"),
            invoice_amount_median=("invoice_amount_median", "median"),
            invoice_payment_delay_median_days=("invoice_payment_delay_median_days", "median"),
            invoice_late_payment_rate=("invoice_late_payment_rate", "median"),
            invoice_severe_late_rate_90dpd=("invoice_severe_late_rate_90dpd", "median"),
            invoice_top_customer_concentration_pct=("invoice_top_customer_concentration_pct", "median"),
            invoice_dilution_proxy_rate=("invoice_dilution_proxy_rate", "median"),
        )
        .sort_values("industry")
        .reset_index(drop=True)
    )
    benchmark_df["invoice_benchmark_source"] = "Financial Statement Analysis public company proxy receivables benchmarks"
    return benchmark_df[
        [
            "industry",
            "invoice_record_count",
            "invoice_customer_count",
            "invoice_amount_median",
            "invoice_payment_delay_median_days",
            "invoice_late_payment_rate",
            "invoice_severe_late_rate_90dpd",
            "invoice_top_customer_concentration_pct",
            "invoice_dilution_proxy_rate",
            "invoice_benchmark_source",
        ]
    ]


def build_executive_summary(
    company: pd.Series,
    fy0: pd.Series,
    scorecard: dict,
    pricing: dict,
    wc_detail: dict,
    zscore_detail: dict,
    merton: dict,
) -> str:
    """Create the report opening paragraph."""
    return (
        f"{company['borrower_name']} has been assessed using two audited annual-report periods "
        f"(FY{company['fy_minus_1_year']} and FY{company['fy0_year']}) under the existing SME cash-flow "
        f"lending toolkit. The FY{company['fy0_year']} profile shows revenue of {fmt_money(fy0['revenue'])}, "
        f"EBITDA of {fmt_money(fy0['ebitda'])}, DSCR of {fmt_multiple(fy0['dscr'])} and debt / EBITDA of "
        f"{fmt_multiple(fy0['debt_to_ebitda'])}. The model returns an internal grade of {scorecard['grade']} "
        f"and an indicative decision of {scorecard['decision']}, a working-capital flag of {wc_detail['flag']}, "
        f"an Altman Z-score of {zscore_detail['zscore']:.3f} and a Merton PD of {fmt_pct(merton['pd'])}. "
        f"Indicative all-in pricing is {fmt_pct(pricing['all_in_rate'])}."
    )


def build_snapshot_table(company_df: pd.DataFrame) -> str:
    """Create a side-by-side financial snapshot table."""
    fy_minus_1 = company_df[company_df["period"] == "FY-1"].iloc[0]
    fy0 = company_df[company_df["period"] == "FY0"].iloc[0]
    headers = ["Metric", f"FY{int(fy_minus_1['fiscal_year'])}", f"FY{int(fy0['fiscal_year'])}"]
    rows = [
        ["Revenue", fmt_money(fy_minus_1["revenue"]), fmt_money(fy0["revenue"])],
        ["EBITDA", fmt_money(fy_minus_1["ebitda"]), fmt_money(fy0["ebitda"])],
        ["EBIT", fmt_money(fy_minus_1["ebit"]), fmt_money(fy0["ebit"])],
        ["NPAT", fmt_money(fy_minus_1["npat"]), fmt_money(fy0["npat"])],
        ["Operating Cash Flow", fmt_money(fy_minus_1["operating_cash_flow"]), fmt_money(fy0["operating_cash_flow"])],
        ["Cash", fmt_money(fy_minus_1["cash"]), fmt_money(fy0["cash"])],
        ["Total Debt", fmt_money(fy_minus_1["total_debt"]), fmt_money(fy0["total_debt"])],
        ["Net Worth", fmt_money(fy_minus_1["net_worth"]), fmt_money(fy0["net_worth"])],
    ]
    return markdown_table(headers, rows)


def build_metric_table(company_df: pd.DataFrame) -> str:
    """Create a credit-metric table for the current year."""
    fy0 = company_df[company_df["period"] == "FY0"].iloc[0]
    headers = ["Metric", "FY0"]
    rows = [
        ["ICR", fmt_multiple(fy0["icr"])],
        ["DSCR", fmt_multiple(fy0["dscr"])],
        ["FCCR", fmt_multiple(fy0["fccr"])],
        ["Debt / EBITDA", fmt_multiple(fy0["debt_to_ebitda"])],
        ["Current Ratio", fmt_multiple(fy0["current_ratio"])],
        ["Quick Ratio", fmt_multiple(fy0["quick_ratio"])],
        ["Working Capital", fmt_money(fy0["working_capital"])],
        ["Free Cash Flow", fmt_money(fy0["free_cash_flow"])],
    ]
    return markdown_table(headers, rows)


def build_plain_english_ratio_bullets(
    fy0: pd.Series,
    scorecard: dict,
    wc_detail: dict,
    zscore_detail: dict,
    merton: dict,
) -> list[str]:
    """Explain the key ratios in a portfolio-ready credit style."""
    dscr_strength = metric_strength(
        float(fy0["dscr"]),
        BANK_THRESHOLDS["dscr"]["threshold"],
        BANK_THRESHOLDS["dscr"]["direction"],
    )
    icr_strength = metric_strength(
        float(fy0["icr"]),
        BANK_THRESHOLDS["icr"]["threshold"],
        BANK_THRESHOLDS["icr"]["direction"],
    )
    leverage_strength = metric_strength(
        float(fy0["debt_to_ebitda"]),
        BANK_THRESHOLDS["debt_to_ebitda"]["threshold"],
        BANK_THRESHOLDS["debt_to_ebitda"]["direction"],
    )
    current_strength = metric_strength(
        float(fy0["current_ratio"]),
        BANK_THRESHOLDS["current_ratio"]["threshold"],
        BANK_THRESHOLDS["current_ratio"]["direction"],
    )
    quick_strength = metric_strength(
        float(fy0["quick_ratio"]),
        BANK_THRESHOLDS["quick_ratio"]["threshold"],
        BANK_THRESHOLDS["quick_ratio"]["direction"],
    )

    if fy0["dscr"] >= 1.5:
        dscr_comment = "scheduled debt repayments appear comfortably covered by normal operating cash flow."
    elif fy0["dscr"] >= 1.2:
        dscr_comment = "debt repayments are covered, but the cash-flow buffer is only moderate."
    else:
        dscr_comment = "normal operating cash flow does not fully cover scheduled debt service, which is a direct repayment risk."

    if fy0["icr"] >= 3.0:
        icr_comment = "interest expense looks well covered, so a moderate earnings dip should still be manageable."
    elif fy0["icr"] >= 2.0:
        icr_comment = "interest is covered, but there is less room for a profit shock."
    else:
        icr_comment = "interest cover is thin, so the company is more exposed if profit falls."

    if fy0["debt_to_ebitda"] <= 2.0:
        leverage_comment = "debt looks conservative relative to earnings, which usually lowers refinance and downturn risk."
    elif fy0["debt_to_ebitda"] <= 4.0:
        leverage_comment = "leverage is still within a typical bank comfort range, but not especially low."
    else:
        leverage_comment = "debt is stretched relative to earnings, which increases refinancing and earnings-volatility risk."

    if fy0["current_ratio"] >= 1.5:
        current_comment = "short-term obligations appear well covered on paper."
    elif fy0["current_ratio"] >= 1.2:
        current_comment = "short-term liabilities are covered, but the buffer is not large."
    else:
        current_comment = "short-term liquidity is tight, with limited balance-sheet room for a working-capital shock."

    inventory_note = ""
    if wc_detail["inventory_share_of_ca"] >= 0.20:
        inventory_note = (
            f" Inventory represents {fmt_pct(wc_detail['inventory_share_of_ca'])} of current assets, "
            "so liquidity depends materially on turning stock into cash."
        )
    if fy0["quick_ratio"] >= 1.0:
        quick_comment = "even after removing inventory, near-cash assets cover short-term obligations well."
    elif fy0["quick_ratio"] >= 0.8:
        quick_comment = "liquid assets broadly cover short-term obligations without needing to lean heavily on inventory."
    else:
        quick_comment = "the business relies on cash collections, stock turnover or supplier support to stay liquid."

    if fy0["free_cash_flow"] >= 0:
        fcf_comment = "positive free cash flow provides extra room to reduce debt or absorb a weaker trading year."
    else:
        fcf_comment = "negative free cash flow means debt repayment relies more on existing cash balances, refinancing or an earnings rebound."

    wc_flag_comment = {
        "GREEN": "day-to-day trading appears self-funding, so short-term liquidity risk looks lower.",
        "AMBER": "liquidity is currently manageable, but part of the buffer depends on cash remaining on hand.",
        "RED": "the business may need external funding to support normal trading, which is a clear short-term credit concern.",
    }.get(wc_detail["flag"], wc_detail["comment"])

    zscore_comment = {
        "SAFE": "this secondary distress indicator sits in the safe zone, consistent with lower medium-term failure risk.",
        "GREY": "this sits in a middle zone, so the lender would normally want closer monitoring and context.",
        "DISTRESS": "this sits in the distress zone, which is a warning sign for medium-term credit risk.",
    }.get(zscore_detail["zone"], "this is a secondary warning indicator rather than a formal external rating.")

    grade_comment = (
        f"The integrated scorecard gives the company grade {scorecard['grade']} and a model decision of "
        f"{scorecard['decision']}. This should be read as an internal bank-style signal, not a public credit rating."
    )

    return [
        (
            f"DSCR ({fmt_multiple(fy0['dscr'])}, {dscr_strength}): for every A$1 of scheduled interest and principal "
            f"due, the business generated about A${fy0['dscr']:.2f} of operating cash flow. Bank guide: "
            f"{BANK_THRESHOLDS['dscr']['pass']}. Credit read: {dscr_comment}"
        ),
        (
            f"ICR ({fmt_multiple(fy0['icr'])}, {icr_strength}): operating profit covered annual interest about "
            f"{fy0['icr']:.2f} times. Bank guide: {BANK_THRESHOLDS['icr']['pass']}. Credit read: {icr_comment}"
        ),
        (
            f"Debt / EBITDA ({fmt_multiple(fy0['debt_to_ebitda'])}, {leverage_strength}): total debt equals roughly "
            f"{fy0['debt_to_ebitda']:.2f} years of EBITDA. Bank guide: {BANK_THRESHOLDS['debt_to_ebitda']['pass']}. "
            f"Credit read: {leverage_comment}"
        ),
        (
            f"Current Ratio ({fmt_multiple(fy0['current_ratio'])}, {current_strength}): short-term assets covered "
            f"short-term liabilities {fy0['current_ratio']:.2f} times. Bank guide: "
            f"{BANK_THRESHOLDS['current_ratio']['pass']}. Credit read: {current_comment}"
        ),
        (
            f"Quick Ratio ({fmt_multiple(fy0['quick_ratio'])}, {quick_strength}): after removing inventory, cash and "
            f"receivables covered only {fy0['quick_ratio']:.2f} times short-term liabilities. Bank guide: "
            f"{BANK_THRESHOLDS['quick_ratio']['pass']}. Credit read: {quick_comment}{inventory_note}"
        ),
        (
            f"Working Capital ({fmt_money(fy0['working_capital'])}, {wc_detail['flag']}): {wc_detail['comment']}. "
            f"Cash makes up {fmt_pct(wc_detail['cash_share_of_ca'])} of current assets. Credit read: {wc_flag_comment}"
        ),
        (
            f"Free Cash Flow ({fmt_money(fy0['free_cash_flow'])}): this is the cash left after capex and dividends. "
            f"Credit read: {fcf_comment}"
        ),
        (
            f"Altman Z-score ({zscore_detail['zscore']:.3f}, {zscore_detail['zone']} zone) and Merton PD "
            f"({fmt_pct(merton['pd'])}, {pd_risk_band(float(merton['pd']))} modelled default risk): these are "
            f"secondary warning indicators used to sense corporate stress earlier. Credit read: {zscore_comment}"
        ),
        grade_comment,
    ]


def build_plain_english_ratio_section(
    fy0: pd.Series,
    scorecard: dict,
    wc_detail: dict,
    zscore_detail: dict,
    merton: dict,
) -> str:
    """Render the portfolio-oriented ratio interpretation section."""
    intro = (
        "From a credit perspective, the lender is mainly asking three questions: can recurring cash flow service "
        "debt, is total leverage appropriate for the earnings base, and can the company meet short-term obligations "
        "without liquidity stress?"
    )
    bullets = "\n".join(
        f"- {line}"
        for line in build_plain_english_ratio_bullets(fy0, scorecard, wc_detail, zscore_detail, merton)
    )
    return f"{intro}\n\n{bullets}"


def build_trend_summary(trends: pd.DataFrame) -> str:
    """Summarise positive and negative trend flags in one paragraph."""
    positive = trends.loc[trends["status"] == "POSITIVE", "metric"].tolist()
    negative = trends.loc[trends["status"] == "NEGATIVE", "metric"].tolist()
    total = len(trends)
    positive_count = len(positive)

    parts = [f"{positive_count} of {total} monitored metrics improved."]
    if negative:
        parts.append(f"Main watch items are {join_readable(negative)}.")
    else:
        parts.append("No negative trend flags were generated.")
    if positive:
        parts.append(f"Areas improving include {join_readable(positive)}.")
    return " ".join(parts)


def build_source_bullets(source_row: pd.Series) -> list[str]:
    """Return source bullets in a reusable list form."""
    return [
        f"Latest report on file: {source_row['latest_report_file']}",
        f"Prior report on file: {source_row['prior_report_file']}",
        f"Extraction basis: {source_row['analysis_basis']}",
        f"Key assumptions: {source_row['key_assumptions']}",
    ]


def build_source_section(source_row: pd.Series) -> str:
    """Render source and assumption bullets for the report."""
    return "\n".join([
        f"- Latest report on file: `{source_row['latest_report_file']}`",
        f"- Prior report on file: `{source_row['prior_report_file']}`",
        f"- Extraction basis: {source_row['analysis_basis']}",
        f"- Key assumptions: {source_row['key_assumptions']}",
    ])


def build_pdf_blocks(
    company_df: pd.DataFrame,
    source_row: pd.Series,
    scorecard: dict,
    pricing: dict,
    wc_detail: dict,
    zscore_detail: dict,
    merton: dict,
    trends: pd.DataFrame,
) -> list[tuple[str, str]]:
    """Build a structured set of blocks for the PDF renderer."""
    fy0 = company_df[company_df["period"] == "FY0"].iloc[0]
    company_meta = pd.Series({
        "borrower_name": fy0["borrower_name"],
        "fy_minus_1_year": int(company_df[company_df["period"] == "FY-1"]["fiscal_year"].iloc[0]),
        "fy0_year": int(fy0["fiscal_year"]),
    })
    blocks: list[tuple[str, str]] = [
        ("title", f"Credit Review | {fy0['borrower_name']}"),
        ("subtitle", f"Prepared: {date.today().isoformat()}"),
        ("heading", "Executive Summary"),
        ("body", build_executive_summary(company_meta, fy0, scorecard, pricing, wc_detail, zscore_detail, merton)),
        (
            "body",
            "Model note: this toolkit was designed for Australian SME cash-flow lending. For listed corporates, "
            "the outputs should be read as directional internal-credit style signals rather than an external rating opinion.",
        ),
        ("heading", "FY0 Headline Metrics"),
        ("bullet", f"Revenue: {fmt_money(fy0['revenue'])}"),
        ("bullet", f"EBITDA: {fmt_money(fy0['ebitda'])}"),
        ("bullet", f"Operating Cash Flow: {fmt_money(fy0['operating_cash_flow'])}"),
        ("bullet", f"Total Debt: {fmt_money(fy0['total_debt'])}"),
        ("bullet", f"DSCR: {fmt_multiple(fy0['dscr'])}"),
        ("bullet", f"Debt / EBITDA: {fmt_multiple(fy0['debt_to_ebitda'])}"),
        ("bullet", f"Current Ratio: {fmt_multiple(fy0['current_ratio'])}"),
        ("bullet", f"Indicative all-in pricing: {fmt_pct(pricing['all_in_rate'])}"),
        ("heading", "Credit Interpretation of Key Ratios"),
        (
            "body",
            "The lender is primarily assessing repayment capacity, leverage, and short-term liquidity. The notes "
            "below translate the headline ratios into direct credit implications.",
        ),
    ]
    blocks.extend(
        ("bullet", line)
        for line in build_plain_english_ratio_bullets(fy0, scorecard, wc_detail, zscore_detail, merton)
    )
    blocks.extend([
        ("heading", "Trend and Risk Signals"),
        ("body", build_trend_summary(trends)),
        (
            "body",
            f"Working-capital assessment: {wc_detail['flag']} | {wc_detail['comment']}. Cash represents "
            f"{fmt_pct(wc_detail['cash_share_of_ca'])} of current assets.",
        ),
        (
            "body",
            f"Credit quality assessment: Altman Z-score {zscore_detail['zscore']:.3f} ({zscore_detail['zone']}), "
            f"Merton PD {fmt_pct(merton['pd'])}, PVEL {fmt_money(merton['pvel'])}.",
        ),
        ("heading", "Source Documents and Assumptions"),
    ])
    blocks.extend(("bullet", line) for line in build_source_bullets(source_row))
    return blocks


def write_pdf_report(blocks: list[tuple[str, str]], output_path: Path) -> None:
    """Write a simple multi-page PDF without introducing new dependencies."""
    style_map = {
        "title": {"fontsize": 18, "weight": "bold", "width": 70, "line_height": 0.033, "space_before": 0.00, "space_after": 0.010},
        "subtitle": {"fontsize": 9, "weight": "normal", "width": 90, "line_height": 0.019, "space_before": 0.000, "space_after": 0.012},
        "heading": {"fontsize": 12, "weight": "bold", "width": 80, "line_height": 0.024, "space_before": 0.010, "space_after": 0.006},
        "body": {"fontsize": 9.5, "weight": "normal", "width": 100, "line_height": 0.019, "space_before": 0.000, "space_after": 0.006},
        "bullet": {"fontsize": 9.5, "weight": "normal", "width": 96, "line_height": 0.019, "space_before": 0.000, "space_after": 0.004},
    }

    def new_page() -> tuple[plt.Figure, plt.Axes, float]:
        fig, ax = plt.subplots(figsize=(8.27, 11.69))
        ax.set_axis_off()
        return fig, ax, 0.965

    def wrapped_lines(text: str, style: str) -> list[str]:
        config = style_map[style]
        if style == "bullet":
            return wrap(
                text,
                width=config["width"],
                initial_indent="- ",
                subsequent_indent="  ",
                break_long_words=False,
                break_on_hyphens=False,
            ) or [""]
        return wrap(
            text,
            width=config["width"],
            break_long_words=False,
            break_on_hyphens=False,
        ) or [""]

    with PdfPages(output_path) as pdf:
        fig, ax, y = new_page()

        for style, text in blocks:
            config = style_map[style]
            lines = wrapped_lines(text, style)
            required_height = (
                config["space_before"]
                + len(lines) * config["line_height"]
                + config["space_after"]
            )
            if y - required_height < 0.05:
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)
                fig, ax, y = new_page()

            y -= config["space_before"]
            for line in lines:
                ax.text(
                    0.06,
                    y,
                    line,
                    ha="left",
                    va="top",
                    fontsize=config["fontsize"],
                    fontweight=config["weight"],
                    family="DejaVu Sans",
                )
                y -= config["line_height"]
            y -= config["space_after"]

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


def render_credit_report(
    company_df: pd.DataFrame,
    source_row: pd.Series,
    scorecard: dict,
    pricing: dict,
    wc_detail: dict,
    zscore_detail: dict,
    merton: dict,
    trends: pd.DataFrame,
    narrative: str,
) -> str:
    """Build a bank-style markdown report for one selected company."""
    fy0 = company_df[company_df["period"] == "FY0"].iloc[0]
    company_meta = pd.Series({
        "borrower_name": fy0["borrower_name"],
        "fy_minus_1_year": int(company_df[company_df["period"] == "FY-1"]["fiscal_year"].iloc[0]),
        "fy0_year": int(fy0["fiscal_year"]),
    })
    zscore_trend = borrower_zscore_trend(company_df, int(fy0["borrower_id"])).attrs.get("trend_comment", "Z-score trend is stable.")
    trend_summary = build_trend_summary(trends)
    trend_highlights = trends[trends["status"].isin(["POSITIVE", "NEGATIVE"])][["metric", "status"]]
    trend_lines = "\n".join(
        f"- {row['metric']}: {row['status']}"
        for _, row in trend_highlights.iterrows()
    ) or "- No material positive or negative trend flags were generated."

    return (
        f"# Credit Review | {fy0['borrower_name']}\n\n"
        f"Prepared: {date.today().isoformat()}\n\n"
        f"## Executive Summary\n"
        f"{build_executive_summary(company_meta, fy0, scorecard, pricing, wc_detail, zscore_detail, merton)}\n\n"
        f"Model note: this toolkit was designed for Australian SME cash-flow lending. For listed corporates, the outputs should be read as directional internal-credit style signals rather than an external rating opinion.\n\n"
        f"## Financial Snapshot\n"
        f"{build_snapshot_table(company_df)}\n\n"
        f"## FY0 Credit Metrics\n"
        f"{build_metric_table(company_df)}\n\n"
        f"## Credit Interpretation of Key Ratios\n"
        f"{build_plain_english_ratio_section(fy0, scorecard, wc_detail, zscore_detail, merton)}\n\n"
        f"## Key Credit Observations\n"
        f"Earnings and cash generation remain the primary repayment source. {zscore_trend} {pricing['comment']}\n\n"
        f"Trend summary: {trend_summary}\n\n"
        f"Trend flags generated by the toolkit:\n"
        f"{trend_lines}\n\n"
        f"Working-capital assessment: {wc_detail['flag']} | {wc_detail['comment']}. Cash represents {fmt_pct(wc_detail['cash_share_of_ca'])} of current assets.\n\n"
        f"Credit quality assessment: Altman Z-score {zscore_detail['zscore']:.3f} ({zscore_detail['zone']}), Merton PD {fmt_pct(merton['pd'])}, PVEL {fmt_money(merton['pvel'])}.\n\n"
        f"## Automated Committee Narrative\n"
        f"```\n{narrative}\n```\n\n"
        f"## Source Documents and Assumptions\n"
        f"{build_source_section(source_row)}\n"
    )


def write_company_outputs(
    df: pd.DataFrame,
    df_with_ratios: pd.DataFrame,
    source_df: pd.DataFrame,
) -> pd.DataFrame:
    """Run the toolkit per borrower and write tables plus reports."""
    summary_rows: list[dict] = []

    for borrower_id in df["borrower_id"].unique():
        company_df = df[df["borrower_id"] == borrower_id].copy()
        company_df_r = df_with_ratios[df_with_ratios["borrower_id"] == borrower_id].copy()
        fy0 = company_df_r[company_df_r["period"] == "FY0"].iloc[0]
        source_row = source_df[source_df["borrower_name"] == fy0["borrower_name"]].iloc[0]
        year_map = dict(zip(company_df["period"], company_df["fiscal_year"]))
        slug = slugify(fy0["borrower_name"])

        spread = rename_period_columns(spread_borrower(df, borrower_id), year_map)
        ratio_summary = rename_period_columns(borrower_ratio_summary(df_with_ratios, borrower_id), year_map)
        raw_trends = analyse_trends(df_with_ratios, borrower_id)
        trends = rename_period_columns(raw_trends, year_map)
        wc_detail = analyse_working_capital(fy0)
        merton = borrower_merton_analysis(df_with_ratios, borrower_id)
        scorecard = score_borrower(df_with_ratios, borrower_id)
        pricing = compute_pricing(
            facility_amount=float(fy0["total_debt"]),
            pd_value=float(merton["pd"]),
            pvel=float(merton["pvel"]),
            weighted_score=float(scorecard["weighted_score"]),
            debt_to_ebitda=float(fy0["debt_to_ebitda"]),
            wc_flag=wc_detail["flag"],
            icr=float(fy0["icr"]),
            dscr=float(fy0["dscr"]),
        )
        pricing_table = pricing_waterfall_table(pricing)
        comments = generate_automated_comments_table(
            scorecard_result=scorecard,
            trends=raw_trends,
            wc_detail=wc_detail,
            merton=merton,
            zscore_detail=scorecard["zscore_detail"],
            pricing=pricing,
        )
        narrative = generate_borrower_commentary(
            borrower_name=fy0["borrower_name"],
            industry=fy0["industry_folder"],
            revenue_fy0=float(fy0["revenue"]),
            scorecard_result=scorecard,
            trends=raw_trends,
            wc_detail=wc_detail,
            merton=merton,
            zscore_detail=scorecard["zscore_detail"],
            pricing=pricing,
            period_labels=["FY-1", "FY0"],
        )

        spread.to_csv(TABLE_DIR / f"{slug}_spread.csv")
        ratio_summary.to_csv(TABLE_DIR / f"{slug}_ratios.csv")
        trends.to_csv(TABLE_DIR / f"{slug}_trends.csv", index=False)
        scorecard["scorecard_table"].to_csv(TABLE_DIR / f"{slug}_scorecard.csv", index=False)
        comments.to_csv(TABLE_DIR / f"{slug}_automated_comments.csv", index=False)
        pricing_table.to_csv(TABLE_DIR / f"{slug}_pricing_waterfall.csv", index=False)

        report_text = render_credit_report(
            company_df=company_df_r,
            source_row=source_row,
            scorecard=scorecard,
            pricing=pricing,
            wc_detail=wc_detail,
            zscore_detail=scorecard["zscore_detail"],
            merton=merton,
            trends=trends,
            narrative=narrative,
        )
        (REPORT_DIR / f"{slug}_credit_report.md").write_text(report_text, encoding="utf-8")
        write_pdf_report(
            build_pdf_blocks(
                company_df=company_df_r,
                source_row=source_row,
                scorecard=scorecard,
                pricing=pricing,
                wc_detail=wc_detail,
                zscore_detail=scorecard["zscore_detail"],
                merton=merton,
                trends=trends,
            ),
            PDF_DIR / f"{slug}_credit_report.pdf",
        )

        summary_rows.append({
            "borrower_id": int(borrower_id),
            "borrower_name": fy0["borrower_name"],
            "industry_folder": fy0["industry_folder"],
            "latest_fiscal_year": int(fy0["fiscal_year"]),
            "revenue_fy0": float(fy0["revenue"]),
            "ebitda_fy0": float(fy0["ebitda"]),
            "operating_cash_flow_fy0": float(fy0["operating_cash_flow"]),
            "icr_fy0": float(fy0["icr"]),
            "dscr_fy0": float(fy0["dscr"]),
            "debt_to_ebitda_fy0": float(fy0["debt_to_ebitda"]),
            "current_ratio_fy0": float(fy0["current_ratio"]),
            "working_capital_flag": wc_detail["flag"],
            "zscore_fy0": float(scorecard["zscore_detail"]["zscore"]),
            "zscore_zone": scorecard["zscore_detail"]["zone"],
            "merton_pd_fy0": float(merton["pd"]),
            "pvel_fy0": float(merton["pvel"]),
            "weighted_score": float(scorecard["weighted_score"]),
            "grade": scorecard["grade"],
            "decision": scorecard["decision"],
            "all_in_rate": float(pricing["all_in_rate"]),
        })

    summary_df = pd.DataFrame(summary_rows).sort_values(["industry_folder", "borrower_name"])
    summary_df.to_csv(TABLE_DIR / "public_company_credit_summary.csv", index=False)
    return summary_df


def write_portfolio_report(summary_df: pd.DataFrame) -> None:
    """Write a short overview report covering all selected companies."""
    rows = []
    for _, row in summary_df.iterrows():
        rows.append([
            row["borrower_name"],
            row["industry_folder"],
            fmt_pct(row["merton_pd_fy0"]),
            row["grade"],
            row["decision"],
            fmt_pct(row["all_in_rate"]),
        ])

    report = (
        "# Public Company Credit Portfolio Overview\n\n"
        "This file summarises the five selected listed companies analysed from the annual-report dataset. "
        "Each company also has a standalone markdown credit review in this folder, a PDF version in the project root, "
        "and detailed csv tables in `outputs/tables/public_company_analysis`.\n\n"
        + markdown_table(
            ["Company", "Industry", "Merton PD", "Grade", "Decision", "Indicative All-in Rate"],
            rows,
        )
        + "\n"
    )
    (REPORT_DIR / "portfolio_overview.md").write_text(report, encoding="utf-8")
    write_pdf_report(
        [
            ("title", "Public Company Credit Portfolio Overview"),
            (
                "body",
                "This summary covers the five listed companies analysed from the annual-report dataset. Each "
                "company also has a standalone PDF credit report in the project root.",
            ),
            *[
                (
                    "bullet",
                    f"{row['borrower_name']} | {row['industry_folder']} | Grade {row['grade']} | Decision "
                    f"{row['decision']} | Merton PD {fmt_pct(row['merton_pd_fy0'])} | Indicative all-in rate "
                    f"{fmt_pct(row['all_in_rate'])}",
                )
                for _, row in summary_df.iterrows()
            ],
        ],
        ROOT_PDF_DIR / "portfolio_overview.pdf",
    )


def main() -> None:
    """Run the public-company analysis workflow."""
    ensure_output_dirs()
    df = pd.read_csv(INPUT_PATH)
    source_df = pd.read_csv(SOURCE_PATH)
    df_with_ratios = calculate_ratios(df)
    listed_standard_df, listed_benchmark_df = build_cashflow_lending_public_benchmark_exports(df_with_ratios)

    # Persist the curated input set alongside the outputs for downstream reuse.
    df_with_ratios.to_csv(TABLE_DIR / "public_listed_company_financials_with_ratios.csv", index=False)
    listed_standard_df.to_csv(TABLE_DIR / "public_listed_company_financials_standardized.csv", index=False)
    listed_benchmark_df.to_csv(TABLE_DIR / "public_listed_company_benchmarks.csv", index=False)
    source_df.to_csv(TABLE_DIR / "public_listed_company_sources.csv", index=False)

    summary_df = write_company_outputs(df, df_with_ratios, source_df)
    transaction_benchmark_df = build_cashflow_lending_transaction_benchmarks(df_with_ratios, summary_df)
    invoice_benchmark_df = build_cashflow_lending_invoice_benchmarks(df_with_ratios, summary_df)
    transaction_benchmark_df.to_csv(TABLE_DIR / "public_transaction_benchmarks.csv", index=False)
    invoice_benchmark_df.to_csv(TABLE_DIR / "public_invoice_benchmarks.csv", index=False)
    write_portfolio_report(summary_df)


if __name__ == "__main__":
    main()
