"""Page 2 — Pricing & Competitor Intelligence."""

import streamlit as st

from pricing_intel.config import PARITY_TOLERANCE
from pricing_intel.metrics import safe_divide
from pricing_intel.ui import charts, state
from pricing_intel.ui import components as ui
from pricing_intel.ui import formatting as fmt

ctx = state.page_context()
ui.page_header(
    "Pricing & Competitor Intelligence",
    "How our prices compare with tracked competitor prices, and how volume and margin differ by price position.",
    eyebrow="Pricing",
    badges=ctx.badges,
)

if state.require_rows(ctx):
    df = ctx.df
    has_comp = df["competitor_price"].notna()

    if not has_comp.any():
        ui.empty_state("No competitor prices in this selection",
                       "Competitor analysis needs the optional competitor_price column. "
                       "Price history is still shown below.")
    else:
        kpi = ctx.db.query("kpi_summary", ctx.filters).iloc[0]
        comp_rows = df[has_comp]
        below = safe_divide(comp_rows.loc[comp_rows["competitor_gap_pct"] < -PARITY_TOLERANCE, "units_sold"].sum(),
                            comp_rows["units_sold"].sum())
        above = safe_divide(comp_rows.loc[comp_rows["competitor_gap_pct"] > PARITY_TOLERANCE, "units_sold"].sum(),
                            comp_rows["units_sold"].sum())
        ui.kpi_row([
            ui.Kpi("Avg price gap vs competitor", fmt.pct(kpi["avg_competitor_gap_pct"], signed=True),
                   sub="Units-weighted; + means we are pricier",
                   help="Σ(gap % × units) ÷ Σ units, over rows with a competitor price only."),
            ui.Kpi("Units sold below competitor", fmt.pct(below),
                   sub=f"More than {PARITY_TOLERANCE:.0%} cheaper"),
            ui.Kpi("Units sold above competitor", fmt.pct(above),
                   sub=f"More than {PARITY_TOLERANCE:.0%} pricier"),
            ui.Kpi("Competitor price coverage", fmt.pct(kpi["competitor_coverage"]),
                   sub="Share of units with a tracked price",
                   help="Rows without a competitor price are excluded from gap metrics, never treated as zero."),
        ])

        bands = ctx.db.query("competitor_position", ctx.filters)
        ui.section("Performance by price position",
                   "Weekly rows grouped by our price relative to the competitor "
                   f"(parity = within ±{PARITY_TOLERANCE:.0%}).")
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            ui.show_chart(charts.band_bars(bands, "price_band", "avg_units_per_week",
                                           "Average units per product-week", "number", "Units / week",
                                           ordinal=False))
        with c2:
            ui.show_chart(charts.band_bars(bands, "price_band", "gross_margin_pct",
                                           "Gross margin", "pct", "Gross margin", ordinal=False))
        st.caption("Bands mix different products and categories, and cheaper weeks often coincide with promotions "
                   "and peak season. Read these as descriptive comparisons, not the effect of price. "
                   "The Demand & Price Elasticity page controls for those factors.")

        gap = ctx.db.query("category_platform_gap", ctx.filters)
        if len(gap):
            pivot = gap.pivot(index="category", columns="platform", values="avg_gap_pct")
            ui.section("Price gap by category and channel",
                       "Blue = cheaper than competitor, red = pricier, grey ≈ parity.")
            ui.show_chart(charts.heatmap(pivot, "Average price gap vs competitor (units-weighted)",
                                         colorbar_title="Gap"))

        ui.section("Product price positioning",
                   "Each bubble is a product: our average selling price vs the competitor's. "
                   "Above the line means we are pricier. Bubble size = units sold.")
        w = comp_rows.assign(rev=comp_rows["selling_price"] * comp_rows["units_sold"],
                             comp_rev=comp_rows["competitor_price"] * comp_rows["units_sold"])
        prod = w.groupby(["product_id", "product_name", "category"], as_index=False).agg(
            rev=("rev", "sum"), comp_rev=("comp_rev", "sum"), units=("units_sold", "sum"))
        prod = prod[prod["units"] > 0]
        prod["avg_price"] = prod["rev"] / prod["units"]
        prod["avg_comp"] = prod["comp_rev"] / prod["units"]
        prod["gap_pct"] = prod["avg_price"] / prod["avg_comp"] - 1
        cats = sorted(prod["category"].unique())
        highlight = st.selectbox("Highlight category", ["All categories"] + cats, key="pricing_highlight")
        ui.show_chart(charts.price_vs_competitor_scatter(prod, None if highlight == "All categories" else highlight))

        with st.expander("Products with the largest gaps"):
            cols = {"product_name": "Product", "category": "Category",
                    "avg_price": st.column_config.NumberColumn("Our avg price", format="₹%,.0f"),
                    "avg_comp": st.column_config.NumberColumn("Competitor avg", format="₹%,.0f"),
                    "gap_pct": st.column_config.NumberColumn("Gap", format="percent"),
                    "units": st.column_config.NumberColumn("Units", format="%,d")}
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Most expensive vs competitor**")
                ui.show_table(prod.nlargest(8, "gap_pct")[list(cols)], cols)
            with c2:
                st.markdown("**Cheapest vs competitor**")
                ui.show_table(prod.nsmallest(8, "gap_pct")[list(cols)], cols)

    ui.section("Product price history", "Weekly selling, list and competitor prices for one product and channel.")
    products = (df.groupby(["product_id", "product_name"])["revenue"].sum()
                .sort_values(ascending=False).reset_index())
    labels = {r.product_id: f"{r.product_name} ({r.product_id})" for r in products.itertuples()}
    c1, c2 = st.columns([3, 2])
    with c1:
        pid = st.selectbox("Product", list(labels), format_func=labels.get, key="pricing_product",
                           help="Sorted by revenue in the current selection. Type to search.")
    with c2:
        plats = sorted(df.loc[df["product_id"] == pid, "platform"].unique())
        plat = st.selectbox("Platform", plats, key="pricing_platform")
    hist = df[(df["product_id"] == pid) & (df["platform"] == plat)].sort_values("date")
    if hist.empty:
        ui.empty_state("No history for this product and platform")
    else:
        ui.show_chart(charts.price_history(hist, f"{labels[pid]} · {plat}"))
        promo_note = " Orange bars are promotion weeks." if hist["promo_flag"].notna().any() else ""
        ui.show_chart(charts.units_history(hist, "Units sold per week"))
        st.caption("Gaps in the competitor line are weeks without a tracked competitor price." + promo_note)
