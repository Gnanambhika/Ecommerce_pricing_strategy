"""Page 5 — Pricing Scenario Simulator."""

import pandas as pd
import streamlit as st

from pricing_intel.config import BASELINE_WEEKS, CURRENCY_SYMBOL, EXTRAPOLATION_LIMIT
from pricing_intel.elasticity import check_feasibility
from pricing_intel.scenario import (
    Baseline,
    ScenarioInputError,
    ScenarioInputs,
    baseline_from_data,
    model_optimal_price,
    profit_curve,
    run_scenario,
)
from pricing_intel.ui import analysis_cache, charts, state
from pricing_intel.ui import components as ui
from pricing_intel.ui import formatting as fmt

DEFAULT_ELASTICITY = -1.5

ctx = state.page_context()
ui.page_header(
    "Pricing Scenario Simulator",
    "Test what-if price, cost and demand assumptions against an observed baseline. "
    "Outputs are **model simulations under your assumptions**, not forecasts or guaranteed results.",
    eyebrow="Scenarios",
    badges=ctx.badges + [("Simulated outcomes", "sim")],
)

if state.require_rows(ctx):
    df = ctx.df

    # --- Scope ---------------------------------------------------------------
    ui.section("1 · Choose what to simulate",
               f"The baseline is the last {BASELINE_WEEKS} weeks of the selection (global filters apply).")
    c1, c2, c3 = st.columns(3)
    with c1:
        category = st.selectbox("Category", sorted(df["category"].unique()), key="sim_category")
    cat_df = df[df["category"] == category]
    with c2:
        prod_names = (cat_df.groupby(["product_id", "product_name"])["revenue"].sum()
                      .sort_values(ascending=False).reset_index())
        options = ["__all__"] + list(prod_names["product_id"])
        names = dict(zip(prod_names["product_id"], prod_names["product_name"], strict=True))
        product = st.selectbox("Product", options, key="sim_product",
                               format_func=lambda p: "All products in category" if p == "__all__" else names[p])
    scope = cat_df if product == "__all__" else cat_df[cat_df["product_id"] == product]
    with c3:
        plats = ["__all__"] + sorted(scope["platform"].unique())
        platform = st.selectbox("Platform", plats, key="sim_platform",
                                format_func=lambda p: "All platforms" if p == "__all__" else p)
    if platform != "__all__":
        scope = scope[scope["platform"] == platform]

    baseline = baseline_from_data(scope, BASELINE_WEEKS)
    if baseline is None:
        ui.empty_state("No sales in the baseline window", "Pick a different product, platform or date range.")
        st.stop()

    weekly = scope.groupby("date").agg(rev=("revenue", "sum"), units=("units_sold", "sum"))
    weekly = weekly[weekly["units"] > 0]
    weekly_asp = weekly["rev"] / weekly["units"]
    observed_range = (float(weekly_asp.min()), float(weekly_asp.max()))
    aggregate = product == "__all__"

    ui.kpi_row([
        ui.Kpi("Baseline avg price", fmt.currency(baseline.price, compact=False),
               sub="Units-weighted ASP" if aggregate else "Units-weighted average"),
        ui.Kpi("Baseline units / week", fmt.integer(baseline.units)),
        ui.Kpi("Baseline unit cost", fmt.currency(baseline.unit_cost, compact=False)),
        ui.Kpi("Baseline gross profit / week", fmt.currency(baseline.gross_profit),
               sub=f"Margin {fmt.pct(baseline.gross_profit / baseline.revenue if baseline.revenue else float('nan'))}"),
    ])
    if aggregate:
        st.caption("Category-level scope applies the same percentage change to every product and uses the "
                   "units-weighted average price, so it assumes the product mix stays constant.")

    # --- Elasticity default ------------------------------------------------------
    est_row = None
    if check_feasibility(df).ok:
        est = analysis_cache.elasticities(ctx.dataset.key, ctx.filters, df)
        match = est[(est["group"] == category) & est["elasticity"].notna()]
        est_row = match.iloc[0] if len(match) else None
    default_e = round(float(est_row["elasticity"]), 2) if est_row is not None else DEFAULT_ELASTICITY
    default_e = min(max(default_e, -6.0), 1.0)

    # --- Inputs ------------------------------------------------------------------
    ui.section("2 · Set assumptions")
    i1, i2 = st.columns(2, gap="large")
    with i1:
        mode = "Change by %"
        if not aggregate:
            mode = st.radio("Price input", ["Change by %", "Set new price"], horizontal=True, key="sim_mode")
        if mode == "Set new price":
            new_price = st.number_input(f"New selling price ({CURRENCY_SYMBOL})", min_value=1.0,
                                        value=float(round(baseline.price)), step=10.0, key="sim_price_abs")
        else:
            price_change = st.slider(
                "Price change", -50, 50, 0, 1, format="%d%%", key="sim_price_pct",
                help=f"Changes beyond ±{EXTRAPOLATION_LIMIT:.0%} trigger an extrapolation warning.",
            )
            new_price = baseline.price * (1 + price_change / 100)
        cost_change = st.slider("Unit cost change", -30, 30, 0, 1, format="%d%%", key="sim_cost_pct",
                                help="E.g. a supplier price increase or a freight saving.")
        new_cost = baseline.unit_cost * (1 + cost_change / 100)
    with i2:
        elasticity = st.number_input(
            "Price elasticity of demand", min_value=-6.0, max_value=1.0, value=default_e, step=0.05,
            key=f"sim_elasticity_{category}",
            help="% change in units for a 1% change in price. Negative = demand falls as price rises.",
        )
        if est_row is not None:
            st.caption(f"Default is this category's estimate: {est_row['elasticity']:.2f} "
                       f"(95% CI {est_row['ci_low']:.2f} to {est_row['ci_high']:.2f}). Edit to test other values.")
        else:
            st.caption(f"No estimate available for this selection; default {DEFAULT_ELASTICITY} is an "
                       "illustrative assumption. Edit it to match your own evidence.")
        shift = st.slider("Other demand change (not price-driven)", -50, 50, 0, 1, format="%d%%",
                          key="sim_shift", help="Assumed change from seasonality, marketing or market growth.")

    inputs = ScenarioInputs(baseline, float(new_price), float(new_cost), float(elasticity), shift / 100,
                            observed_range)
    try:
        result = run_scenario(inputs)
    except ScenarioInputError as exc:
        st.error(f"Invalid input: {exc}")
        st.stop()

    # --- Results -----------------------------------------------------------------
    ui.section("3 · Simulated outcome (per week)", "Change versus the observed baseline.")
    s, chg, pc = result.scenario, result.change, result.pct_change

    def d(key, higher=True):
        return fmt.pct(pc[key], signed=True), ui.delta_sentiment(chg[key], higher)

    ui.kpi_row([
        ui.Kpi("Scenario price", fmt.currency(s["price"], compact=False), fmt.pct(pc["price"], signed=True)),
        ui.Kpi("Estimated units", fmt.integer(s["units"]), *d("units")),
        ui.Kpi("Scenario revenue", fmt.currency(s["revenue"]), *d("revenue")),
        ui.Kpi("Scenario gross profit", fmt.currency(s["gross_profit"]), *d("gross_profit")),
        ui.Kpi("Scenario gross margin", fmt.pct(s["gross_margin_pct"]), fmt.pp(chg["gross_margin_pct"]),
               ui.delta_sentiment(chg["gross_margin_pct"])),
    ])
    for w in result.warnings:
        st.warning(w)

    if pd.notna(result.break_even_units) and (abs(chg["price"]) > 1e-9 or abs(chg["unit_cost"]) > 1e-9):
        ui.insight(
            f"Break-even check: to keep weekly gross profit at the baseline "
            f"{fmt.currency(result.baseline['gross_profit'])} at the scenario price and cost, units would need to "
            f"change by **{fmt.pct(result.break_even_volume_change, signed=True)}** "
            f"(to {fmt.integer(result.break_even_units)}/week). The model assumes "
            f"**{fmt.pct(pc['units'], signed=True)}**."
        )

    c1, c2 = st.columns([3, 2], gap="medium")
    with c1:
        curve = profit_curve(Baseline(baseline.price, baseline.units, baseline.unit_cost), new_cost,
                             elasticity, shift / 100, span=0.5)
        opt = model_optimal_price(new_cost, elasticity)
        ui.show_chart(charts.profit_curve(curve, baseline.price, new_price, opt if pd.notna(opt) else None))
    with c2:
        ui.show_chart(charts.baseline_vs_scenario(result.baseline, result.scenario))

    if est_row is not None and pd.notna(est_row["ci_low"]):
        ui.section("Sensitivity to the elasticity estimate",
                   "The same scenario evaluated at the ends of the 95% confidence interval.")
        rows = []
        for label, e in (("Lower CI (more price-sensitive)", est_row["ci_low"]), ("Estimate", est_row["elasticity"]),
                         ("Upper CI (less price-sensitive)", est_row["ci_high"])):
            e = float(min(max(e, -6.0), 1.0))
            r = run_scenario(ScenarioInputs(baseline, float(new_price), float(new_cost), e, shift / 100))
            rows.append({"Assumption": label, "Elasticity": e, "Units / week": r.scenario["units"],
                         "Gross profit / week": r.scenario["gross_profit"],
                         "GP change": r.pct_change["gross_profit"]})
        ui.show_table(pd.DataFrame(rows), column_config={
            "Elasticity": st.column_config.NumberColumn(format="%.2f"),
            "Units / week": st.column_config.NumberColumn(format="%,.0f"),
            "Gross profit / week": st.column_config.NumberColumn(format="₹%,.0f"),
            "GP change": st.column_config.NumberColumn(format="percent"),
        })

    with st.expander("Assumptions and limitations"):
        st.markdown(
            f"""
- **Demand model:** units = baseline units × (new price ÷ baseline price)^elasticity × (1 + other demand change).
  Constant elasticity is a local approximation, credible only near observed prices
  (observed weekly average price here: {fmt.currency(observed_range[0], compact=False)} to
  {fmt.currency(observed_range[1], compact=False)}).
- **Held constant:** competitor prices, product mix, promotion calendar, stock availability, marketplace fees.
  Competitors may respond to our price changes; the model does not anticipate that.
- **Gross profit only:** shipping, advertising, fees, returns, taxes and operating costs are excluded, so a
  higher gross profit does not necessarily mean higher net profit.
- **Model optimum** (shown only when elasticity < −1): price = cost × e ÷ (1 + e). It is a property of the
  formula, not a recommendation. Validate any change with a controlled test before rollout.
- Baseline = last {BASELINE_WEEKS} weeks in the current selection, averaged per week.
            """
        )
