"""Page 6 — Data Quality & Methodology."""

import pandas as pd
import streamlit as st

from pricing_intel.config import MAX_UPLOAD_MB, MESSY_SAMPLE_PATH, SYNTHETIC_NOTICE, TEMPLATE_PATH
from pricing_intel.data_io import load_and_validate
from pricing_intel.db import QUERY_FILES, load_sql
from pricing_intel.schema import data_dictionary
from pricing_intel.ui import charts, state
from pricing_intel.ui import components as ui
from pricing_intel.ui import formatting as fmt
from pricing_intel.validation import ValidationError, ValidationResult

ctx = state.page_context()
ds = ctx.dataset
ui.page_header(
    "Data Quality & Methodology",
    "Where the data comes from, how it was validated, how every metric is defined, and how to import your own CSV.",
    eyebrow="Trust & transparency",
    badges=[b for b in ctx.badges if b[1] in ("synthetic", "")][:1],
)

SEVERITY_LABEL = {"error": "⛔ Removed", "warning": "⚠️ Kept / repaired", "info": "ℹ️ Info"}


def render_report(result: ValidationResult, key: str) -> None:
    s = result.summary
    ui.kpi_row([
        ui.Kpi("Rows received", fmt.integer(s["rows_in"])),
        ui.Kpi("Rows kept", fmt.integer(s["rows_out"]), sub=f"{fmt.pct(s['retained_pct'])} retained"),
        ui.Kpi("Products", fmt.integer(s["products"]), sub=f"{s['categories']} categories · {s['brands']} brands"),
        ui.Kpi("Periods", fmt.integer(s["periods"]),
               sub=f"{s['date_min']:%d %b %Y} – {s['date_max']:%d %b %Y}"),
        ui.Kpi("Competitor price coverage", fmt.pct(s["competitor_coverage"]), sub="Share of rows"),
    ])
    if s["single_snapshot"]:
        st.warning("This dataset has a single date. Elasticity analysis will be disabled; "
                   "pricing, margin and competitor views still work.")
    issues = result.issues_frame
    c1, c2 = st.columns([3, 2], gap="medium")
    with c1:
        st.markdown("**Validation log**")
        if issues.empty:
            st.success("All checks passed. No rows were removed or repaired.")
        else:
            issues = issues.assign(severity=issues["severity"].map(SEVERITY_LABEL))
            ui.show_table(issues, column_config={
                "check": "Check", "severity": "Outcome", "rows": st.column_config.NumberColumn("Rows", format="%,d"),
                "action": "Action", "detail": "Detail"})
    with c2:
        ui.show_chart(charts.completeness_bar(s["completeness"]), key=f"completeness_{key}")


@st.cache_data(show_spinner="Validating file…", max_entries=8)
def _validate_upload(key: str, data: bytes):
    try:
        return load_and_validate(data), None
    except ValidationError as exc:
        return None, str(exc)


# --- Active dataset ----------------------------------------------------------
ui.section("Active dataset")
if ds.synthetic:
    st.info(f"**{ds.label}.** {SYNTHETIC_NOTICE}")
else:
    c1, c2 = st.columns([4, 1])
    c1.success(f"**{ds.label}**. Processed in memory for this browser session only; nothing is saved or shared.")
    if c2.button("Switch back to sample data", type="secondary"):
        state.clear_uploaded()
        st.rerun()
render_report(ds.result, "active")

# --- Import -------------------------------------------------------------------
ui.section("Import your own CSV",
           "One row per date × product × platform. Required and optional columns are listed in the data "
           "dictionary below. Common header variants (e.g. MRP, SKU, Qty) are mapped automatically.")
c1, c2, _ = st.columns([1, 1, 2])
with c1:
    st.download_button("Download template", TEMPLATE_PATH.read_bytes(), "import_template.csv", "text/csv",
                       help="Headers in the exact expected format with three example rows.")
with c2:
    if MESSY_SAMPLE_PATH.exists():
        st.download_button("Download a messy example", MESSY_SAMPLE_PATH.read_bytes(),
                           "messy_import_example.csv", "text/csv",
                           help="A deliberately broken file to see the validation rules in action.")
uploaded = st.file_uploader(f"Upload CSV (max {MAX_UPLOAD_MB} MB)", type=["csv"], key="uploader",
                            help="Processed in memory for your session. Do not upload confidential data to a "
                                 "public deployment.")
if uploaded is not None:
    data = uploaded.getvalue()
    key = state.dataset_key_for_bytes(data)
    result, error = _validate_upload(key, data)
    if error:
        st.error(f"**This file can't be used:** {error}")
    elif ds.key == key:
        st.success("This file is the active dataset; its validation report is shown above. All pages now use it.")
    else:
        st.markdown(f"**Validation report for `{uploaded.name}`**")
        render_report(result, "upload")
        if st.button("Use this dataset in the app", type="primary"):
            state.set_uploaded(key, uploaded.name, result)
            st.rerun()

# --- Dictionary & definitions ----------------------------------------------------
ui.section("Data dictionary")
ui.show_table(pd.DataFrame(data_dictionary()))

ui.section("Metric definitions", "Percentages are computed from totals (ratio of sums), never averaged across rows.")
definitions = pd.DataFrame([
    ("Revenue", "Σ selling_price × units_sold", "Net of discounts; before returns, taxes and fees."),
    ("Cost of goods sold (COGS)", "Σ unit_cost × units_sold", "Landed product cost only."),
    ("Gross profit", "Revenue − COGS", "Before shipping, advertising, marketplace fees, returns, taxes and opex."),
    ("Gross margin %", "Gross profit ÷ Revenue", "Blank when revenue is zero."),
    ("Average selling price (ASP)", "Revenue ÷ Units", "Units-weighted; blank when units are zero."),
    ("Discount %", "(original_price − selling_price) ÷ original_price", "Per row; negative = above list price."),
    ("Effective discount rate", "1 − Revenue ÷ Σ(original_price × units)", "Revenue-weighted discount depth."),
    ("Discount investment", "Σ (original_price − selling_price) × units", "Foregone list-price revenue."),
    ("Competitor price gap %", "(selling_price − competitor_price) ÷ competitor_price",
     "+ = we are pricier. Rows without a competitor price are excluded, never treated as zero."),
    ("Avg competitor gap", "Σ(gap % × units) ÷ Σ units over rows with a competitor price", "Units-weighted."),
    ("Price position", "Below / parity (±2%) / above competitor", "Based on gap %."),
    ("Rankings", "SQL RANK() on gross profit (overall and PARTITION BY category)", "Ties share a rank."),
], columns=["Metric", "Definition", "Notes"])
ui.show_table(definitions)
st.markdown(
    "**Excluded from all profit figures:** shipping and fulfilment, advertising, marketplace commissions and "
    "payment fees, returns and refunds, taxes (GST/VAT) and operating expenses. Gross margin is therefore an "
    "upper bound on contribution margin, not net profit."
)

with st.expander("SQL used by the app"):
    st.caption("Each query runs on an in-memory SQLite database. Filters are added as bound parameters.")
    name = st.selectbox("Query", list(QUERY_FILES), format_func=lambda n: n.replace("_", " ").title())
    st.code(load_sql(name), language="sql")

with st.expander("Synthetic data generation"):
    st.markdown(
        """
The sample data is produced by `scripts/generate_data.py` (seed 42): 120 fictional products in 6 categories,
sold on 3 fictional channels over 78 weeks. Demand follows a constant-elasticity model with a known elasticity
per category, plus seasonality, a festive peak, trend, competitor promotions, random noise and occasional
low-stock weeks. Promotions are more frequent during the festive peak on purpose: this creates the classic
confounder that the elasticity method must handle. Around 8% of product-channel series have no competitor
price, and about 5% of other weeks are missing one, to mimic real tracking gaps.

None of these numbers describe real brands, marketplaces or customers.
        """
    )
