"""Page 3 — Discount & Profitability Analysis."""

import plotly.graph_objects as go
import streamlit as st

from pricing_intel.metrics import safe_divide
from pricing_intel.ui import charts, state
from pricing_intel.ui import components as ui
from pricing_intel.ui import formatting as fmt
from pricing_intel.ui import theme as t

ctx = state.page_context()
ui.page_header(
    "Discount & Profitability Analysis",
    "How deep we discount, what it costs in margin, and how concentrated gross profit is.",
    eyebrow="Profitability",
    badges=ctx.badges,
)

if state.require_rows(ctx):
    df = ctx.df
    kpi = ctx.db.query("kpi_summary", ctx.filters).iloc[0]
    has_promo = df["promo_flag"].notna().any()

    promo_rev_share = safe_divide(df.loc[df["promo_flag"] == 1, "revenue"].sum(), df["revenue"].sum()) \
        if has_promo else float("nan")
    promo_gm = safe_divide(df.loc[df["promo_flag"] == 1, "gross_profit"].sum(),
                           df.loc[df["promo_flag"] == 1, "revenue"].sum()) if has_promo else float("nan")
    reg_gm = safe_divide(df.loc[df["promo_flag"] == 0, "gross_profit"].sum(),
                         df.loc[df["promo_flag"] == 0, "revenue"].sum()) if has_promo else float("nan")
    below_cost = df[df["selling_price"] < df["unit_cost"]]

    ui.kpi_row([
        ui.Kpi("Effective discount", fmt.pct(kpi["effective_discount_rate"]),
               help="1 − revenue ÷ (list price × units)."),
        ui.Kpi("Discount investment", fmt.currency(df["discount_amount"].sum()),
               sub="Revenue given up vs list price",
               help="Σ (list price − selling price) × units. Not a cash cost; it is foregone list-price revenue."),
        ui.Kpi("Revenue from promotion weeks", fmt.pct(promo_rev_share),
               sub="Requires promo_flag" if not has_promo else None),
        ui.Kpi("Margin: promotion vs regular", fmt.pp(promo_gm - reg_gm) if has_promo else fmt.DASH,
               sub=f"{fmt.pct(promo_gm)} vs {fmt.pct(reg_gm)}" if has_promo else "Requires promo_flag",
               help="Gross margin in promotion weeks minus gross margin in regular weeks."),
        ui.Kpi("Rows sold below cost", fmt.integer(len(below_cost)),
               sub=f"{below_cost['product_id'].nunique()} product(s)",
               help="Product-weeks where selling price < unit cost (negative gross profit)."),
    ])

    bands = ctx.db.query("discount_bands", ctx.filters)
    ui.section("Discount depth: volume vs margin",
               "Each product-week is placed in a band by its discount from list price (SQL CASE banding).")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        ui.show_chart(charts.band_bars(bands, "discount_band", "avg_units_per_week",
                                       "Average units per product-week", "number", "Units / week"))
    with c2:
        ui.show_chart(charts.band_bars(bands, "discount_band", "gross_margin_pct", "Gross margin", "pct",
                                       "Gross margin"))
    st.caption("Deeper-discount weeks sell more units on average but at lower margin. Volume differences also "
               "reflect *when* discounts run (festive peaks) and which products are discounted, so they "
               "overstate the pure price effect.")

    if has_promo:
        pv = ctx.db.query("promo_vs_regular", ctx.filters)
        pv = pv[pv["week_type"] != "Unknown"]
        ui.section("Promotion vs regular weeks by category")
        c1, c2 = st.columns(2, gap="medium")
        for col, metric, title, tick, hover in (
            (c1, "avg_units_per_week", "Average units per product-week", "~s", "%{y:,.1f}"),
            (c2, "gross_margin_pct", "Gross margin", ".0%", "%{y:.1%}"),
        ):
            fig = go.Figure()
            for i, wt in enumerate(["Regular", "Promotion"]):
                d = pv[pv["week_type"] == wt]
                fig.add_trace(go.Bar(name=wt, x=d["category"], y=d[metric],
                                     marker=dict(color=t.CATEGORICAL[i], cornerradius=4),
                                     hovertemplate=f"%{{x}} · {wt}<br>{hover}<extra></extra>"))
            fig.update_layout(title_text=title, barmode="group", height=340, bargroupgap=0.08)
            fig.update_yaxes(tickformat=tick)
            with col:
                ui.show_chart(fig)

    ui.section("Product profitability")
    ranks = ctx.db.query("product_rankings", ctx.filters)
    c1, c2 = st.columns([3, 2], gap="medium")
    with c1:
        cats = sorted(ranks["category"].unique())
        hl = st.selectbox("Highlight category", ["All categories"] + cats, key="disc_highlight")
        ui.show_chart(charts.discount_margin_scatter(ranks, None if hl == "All categories" else hl))
    with c2:
        pareto = ctx.db.query("profit_pareto", ctx.filters)
        st.markdown("&nbsp;", unsafe_allow_html=True)
        st.markdown("&nbsp;", unsafe_allow_html=True)
        ui.show_chart(charts.pareto(pareto))
        top20 = pareto[pareto["product_share"] <= 0.2]
        if len(top20) and len(pareto) >= 10:
            ui.insight(f"The top 20% of products ({len(top20)}) generate "
                       f"**{fmt.pct(top20['cumulative_share'].iloc[-1], 0)}** of gross profit.")

    ui.section("Lowest-margin products", "Candidates for a pricing or cost review, not automatic price increases.")
    low = ranks[ranks["revenue"] > 0].nsmallest(10, "gross_margin_pct")
    ui.show_table(
        low[["product_name", "category", "brand", "revenue", "gross_profit", "gross_margin_pct",
             "effective_discount_rate", "units_sold"]],
        column_config={
            "product_name": "Product", "category": "Category", "brand": "Brand",
            "revenue": st.column_config.NumberColumn("Revenue", format="₹%,.0f"),
            "gross_profit": st.column_config.NumberColumn("Gross profit", format="₹%,.0f"),
            "gross_margin_pct": st.column_config.NumberColumn("Gross margin", format="percent"),
            "effective_discount_rate": st.column_config.NumberColumn("Effective discount", format="percent"),
            "units_sold": st.column_config.NumberColumn("Units", format="%,d"),
        },
    )
