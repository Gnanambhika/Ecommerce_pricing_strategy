"""Page 4 — Demand & Price Elasticity."""

import pandas as pd
import streamlit as st

from pricing_intel.data_generation import TRUE_ELASTICITY
from pricing_intel.elasticity import check_feasibility
from pricing_intel.ui import analysis_cache, charts, state
from pricing_intel.ui import components as ui
from pricing_intel.ui import formatting as fmt

ctx = state.page_context()
ui.page_header(
    "Demand & Price Elasticity",
    "How strongly units responded to price changes in the historical data, after controlling for "
    "product differences and week-specific demand. **Associations, not proven causal effects.**",
    eyebrow="Demand",
    badges=ctx.badges,
)




if state.require_rows(ctx):
    feas = check_feasibility(ctx.df)
    if not feas.ok:
        st.warning("**Elasticity analysis is disabled for this selection.**\n\n" +
                   "\n".join(f"- {r}" for r in feas.reasons))
        st.markdown("Elasticity requires the *same* products observed at *different* prices over time. "
                    "A single price snapshot can show price levels and margins, but it cannot reveal how "
                    "demand responds to price.")
    else:
        est = analysis_cache.elasticities(ctx.dataset.key, ctx.filters, ctx.df)
        ok = est.dropna(subset=["elasticity"])
        pooled = est[est["group"] == "All (pooled)"].iloc[0] if (est["group"] == "All (pooled)").any() else None

        kpis = [
            ui.Kpi("Pooled elasticity", f"{pooled['elasticity']:.2f}" if pooled is not None and
                   pd.notna(pooled["elasticity"]) else fmt.DASH,
                   sub=(f"95% CI {pooled['ci_low']:.2f} to {pooled['ci_high']:.2f}"
                        if pooled is not None and pd.notna(pooled["elasticity"]) else None),
                   help="Two-way fixed-effects estimate across all selected categories."),
            ui.Kpi("Series used", fmt.integer(feas.series), sub=f"{feas.series_with_variation} with price changes",
                   help="A series is one product on one platform."),
            ui.Kpi("Weeks observed", fmt.integer(feas.periods)),
            ui.Kpi("Zero-sales rows excluded", fmt.integer(pooled["zero_rows_dropped"]) if pooled is not None
                   else fmt.DASH, help="log(0) is undefined, so weeks with zero units are excluded."),
        ]
        ui.kpi_row(kpis)

        truth = TRUE_ELASTICITY if ctx.dataset.synthetic else None
        ui.section("Estimates by category",
                   "Points show the fixed-effects estimate with its 95% confidence interval. "
                   "Hollow grey circles show the naive slope without controls."
                   + (" Orange diamonds show the true values built into the synthetic generator, "
                      "a check that the method recovers known answers." if truth else ""))
        if ok.empty:
            ui.empty_state("No category had enough price variation to estimate",
                           "Widen the date range or include more products.")
        else:
            ui.show_chart(charts.elasticity_forest(est, truth))

            table = est.copy()
            if truth:
                table["true_value"] = table["group"].map(truth).astype(float)
            cols = ["group", "elasticity", "ci_low", "ci_high", "naive_elasticity"] + \
                   (["true_value"] if truth else []) + ["n_obs", "n_series", "within_r2", "interpretation"]
            ui.show_table(table[cols], column_config={
                "group": "Category",
                "elasticity": st.column_config.NumberColumn("Elasticity", format="%.2f"),
                "ci_low": st.column_config.NumberColumn("95% CI low", format="%.2f"),
                "ci_high": st.column_config.NumberColumn("95% CI high", format="%.2f"),
                "naive_elasticity": st.column_config.NumberColumn("Naive slope", format="%.2f",
                                                                  help="No controls: correlation only."),
                "true_value": st.column_config.NumberColumn("True (synthetic)", format="%.2f"),
                "n_obs": st.column_config.NumberColumn("Obs.", format="%,d"),
                "n_series": st.column_config.NumberColumn("Series", format="%,d"),
                "within_r2": st.column_config.NumberColumn("Within R²", format="%.2f"),
                "interpretation": "Reading",
            })
            st.caption("How to read: an elasticity of −1.5 means a 1% higher price was associated with about "
                       "1.5% fewer units, comparing a product with itself in other weeks and adjusting for "
                       "week-wide demand. The naive slope compares *different* products, so it mostly "
                       "reflects that pricier products sell fewer units.")

            ui.section("Price–demand relationship",
                       "Binned scatter: observations grouped by how far price was from the product's usual "
                       "level, after removing product and week averages.")
            choices = list(ok["group"])
            group = st.selectbox("Category", choices, key="elasticity_group",
                                 index=len(choices) - 1 if choices else 0)
            sub = ctx.df if group == "All (pooled)" else ctx.df[ctx.df["category"] == group]
            b = analysis_cache.binned(ctx.dataset.key, ctx.filters, group, sub)
            slope = float(ok.loc[ok["group"] == group, "elasticity"].iloc[0])
            if b.empty:
                ui.empty_state("Not enough observations for a binned view")
            else:
                ui.show_chart(charts.binned_scatter(b, slope, f"{group}: price vs units relative to usual"))

    with st.expander("Method, assumptions and limitations", expanded=not feas.ok):
        st.markdown(
            """
**Model.** For each category: `log(units) = β·log(price) + series effect + week effect + error`,
where a *series* is one product on one platform. β is the elasticity. Standard errors are clustered
by series.

**Why fixed effects?** Series effects remove stable differences between products (quality, brand,
typical price level, channel), so β comes from a product's price moving relative to *its own* norm.
Week effects remove anything that lifted or lowered the whole category in that week, such as the
festive season. Without them, promotions that coincide with seasonal peaks look like a much stronger
price response than really exists.

**What is still not controlled (possible confounders):**
- Promotions may be timed when a product is already trending, or come with extra ad spend or better
  on-site placement that the data does not record.
- Competitor price moves (only partly tracked) and competitor promotions.
- Stock-outs cap sales (censored demand), biasing estimates toward zero in low-stock weeks.
- Weeks with zero sales are excluded because log(0) is undefined.
- Cross-product effects: a discount can pull sales from sibling products (cannibalisation) or forward
  from future weeks (pantry loading). Neither is modelled.

**Interpretation.** Estimates describe how sales and prices *moved together* in this historical data
under the stated assumptions. They are not proof that changing price will cause the same response.
A controlled price test (A/B or staggered rollout) is the way to establish causality.
            """
        )
        if ctx.dataset.synthetic:
            st.info("The sample data is synthetic, generated with known elasticities so the method can be "
                    "validated. The values say nothing about real shoppers.")
