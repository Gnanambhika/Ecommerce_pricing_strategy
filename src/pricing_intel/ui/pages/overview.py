"""Page 1 — Executive Overview."""

import pandas as pd
import streamlit as st

from pricing_intel.ui import charts, state
from pricing_intel.ui import components as ui
from pricing_intel.ui import formatting as fmt

ctx = state.page_context()
ui.page_header(
    "Executive Overview",
    "Revenue, gross profit and margin for the current selection, and where profit comes from.",
    eyebrow="Performance",
    badges=ctx.badges,
)

if state.require_rows(ctx):
    with st.spinner("Calculating KPIs…"):
        cur = ctx.db.query("kpi_summary", ctx.filters).iloc[0]
        prev_f = state.previous_period(ctx.filters, ctx.dataset.data["date"].min().date())
        prev = ctx.db.query("kpi_summary", prev_f).iloc[0] if prev_f else None
        has_prev = prev is not None and pd.notna(prev["revenue"]) and prev["revenue"] > 0

    days = (ctx.filters.end_date - ctx.filters.start_date).days + 1 if ctx.filters.start_date else None
    vs = f"vs prior {days} days" if days else ""

    def growth(key: str, higher_is_better: bool = True):
        if not has_prev or pd.isna(prev[key]) or prev[key] == 0:
            return None, "neutral"
        change = cur[key] / prev[key] - 1
        return f"{fmt.pct(change, signed=True)} {vs}", ui.delta_sentiment(change, higher_is_better)

    def pp_change(key: str, higher_is_better: bool = True):
        if not has_prev or pd.isna(prev[key]) or pd.isna(cur[key]):
            return None, "neutral"
        change = cur[key] - prev[key]
        return f"{fmt.pp(change)} {vs}", ui.delta_sentiment(change, higher_is_better)

    rev_d, rev_s = growth("revenue")
    gp_d, gp_s = growth("gross_profit")
    gm_d, gm_s = pp_change("gross_margin_pct")
    u_d, u_s = growth("units_sold")
    asp_d, _ = growth("avg_selling_price")
    disc_d, _ = pp_change("effective_discount_rate")

    ui.kpi_row([
        ui.Kpi("Revenue", fmt.currency(cur["revenue"]), rev_d, rev_s,
               help="Selling price × units sold. Net of discounts, before returns and taxes."),
        ui.Kpi("Gross profit", fmt.currency(cur["gross_profit"]), gp_d, gp_s,
               help="Revenue − cost of goods sold. Excludes shipping, ads, fees, returns, taxes and opex."),
        ui.Kpi("Gross margin", fmt.pct(cur["gross_margin_pct"]), gm_d, gm_s,
               help="Gross profit ÷ revenue."),
        ui.Kpi("Units sold", fmt.compact_number(cur["units_sold"]), u_d, u_s),
        ui.Kpi("Avg selling price", fmt.currency(cur["avg_selling_price"], compact=False), asp_d, "neutral",
               help="Revenue ÷ units: a units-weighted average price."),
        ui.Kpi("Effective discount", fmt.pct(cur["effective_discount_rate"]), disc_d, "neutral",
               help="1 − revenue ÷ (list price × units). Revenue-weighted depth of discounting."),
    ])
    if not has_prev:
        st.caption("Period-over-period changes appear when an equal-length earlier period exists in the data.")

    monthly = ctx.db.query("monthly_trend", ctx.filters)
    monthly["month"] = pd.to_datetime(monthly["month"])
    ui.section("Trend", "Months are grouped by each week's start date, so the first and last month can be partial.")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        ui.show_chart(charts.bar_over_time(monthly, "month", "revenue", "Monthly revenue", hover_label="Revenue"))
    with c2:
        ui.show_chart(charts.line_over_time(monthly, "month", "gross_margin_pct", "Monthly gross margin",
                                            hover_label="Gross margin"))

    cats = ctx.db.query("category_performance", ctx.filters)
    platforms = ctx.db.query("platform_mix", ctx.filters)

    ui.section("Where profit comes from")
    c1, c2 = st.columns([3, 2], gap="medium")
    with c1:
        labels = cats.apply(lambda r: f"{fmt.pct(r.gross_margin_pct, 0)} margin · "
                                      f"{fmt.pct(r.gross_profit_share, 0)} of GP", axis=1)
        ui.show_chart(charts.hbar(cats, "category", "gross_profit", "Gross profit by category", text=labels))
    with c2:
        st.markdown("**Key observations**")
        if len(cats):
            top = cats.iloc[0]
            ui.insight(f"**{top.category}** generated the most gross profit: "
                       f"{fmt.currency(top.gross_profit)} ({fmt.pct(top.gross_profit_share, 0)} of the total) "
                       f"at a {fmt.pct(top.gross_margin_pct)} margin.")
            cats["share_gap"] = cats["gross_profit_share"] - cats["revenue_share"]
            lag = cats.sort_values("share_gap").iloc[0]
            if lag.share_gap < -0.02:
                ui.insight(f"**{lag.category}** accounts for {fmt.pct(lag.revenue_share, 0)} of revenue but only "
                           f"{fmt.pct(lag.gross_profit_share, 0)} of gross profit, the weakest "
                           "revenue-to-profit conversion in the selection.")
        if len(platforms) > 1:
            best = platforms.sort_values("gross_margin_pct", ascending=False).iloc[0]
            worst = platforms.sort_values("gross_margin_pct").iloc[0]
            ui.insight(f"Gross margin ranges from {fmt.pct(worst.gross_margin_pct)} on **{worst.platform}** to "
                       f"{fmt.pct(best.gross_margin_pct)} on **{best.platform}**.")
        if len(monthly) >= 2:
            first, last = monthly.iloc[0], monthly.iloc[-1]
            ui.insight(f"Effective discount moved from {fmt.pct(first.effective_discount_rate)} in "
                       f"{first.month:%b %Y} to {fmt.pct(last.effective_discount_rate)} in {last.month:%b %Y}.")
        st.caption("Observations describe the selected data; they are not causal explanations.")

    ui.section("Top products by gross profit", "Ranked with SQL window functions (overall and within category).")
    top_products = ctx.db.query("product_rankings", ctx.filters).head(10)
    ui.show_table(
        top_products[["overall_rank", "product_name", "category", "brand", "revenue", "gross_profit",
                      "gross_margin_pct", "units_sold", "category_rank"]],
        column_config={
            "overall_rank": st.column_config.NumberColumn("Rank", width="small"),
            "product_name": "Product",
            "category": "Category",
            "brand": "Brand",
            "revenue": st.column_config.NumberColumn("Revenue", format="₹%,.0f"),
            "gross_profit": st.column_config.NumberColumn("Gross profit", format="₹%,.0f"),
            "gross_margin_pct": st.column_config.ProgressColumn("Gross margin", format="percent",
                                                                min_value=0.0, max_value=1.0),
            "units_sold": st.column_config.NumberColumn("Units", format="%,d"),
            "category_rank": st.column_config.NumberColumn("Rank in category", width="small"),
        },
    )

    with st.expander("Channel summary"):
        ui.show_table(platforms, column_config={
            "platform": "Platform",
            "revenue": st.column_config.NumberColumn("Revenue", format="₹%,.0f"),
            "gross_profit": st.column_config.NumberColumn("Gross profit", format="₹%,.0f"),
            "gross_margin_pct": st.column_config.NumberColumn("Gross margin", format="percent"),
            "units_sold": st.column_config.NumberColumn("Units", format="%,d"),
            "avg_selling_price": st.column_config.NumberColumn("ASP", format="₹%,.0f"),
            "revenue_share": st.column_config.NumberColumn("Revenue share", format="percent"),
        })
