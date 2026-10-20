# Methodology

This document explains how every number in the app is produced, which assumptions it rests on and
where it can mislead.

## 1. Data pipeline

```
CSV (sample or upload)
  └─ read_raw_csv()          text columns; UTF-8 / UTF-8-BOM / Windows-1252
      └─ validate_dataframe() headers, aliases, types, missing, invalid, duplicates  → validation log
          └─ PricingDatabase   in-memory SQLite: dim_product + fact_sales
              ├─ sql/*.sql     aggregations, CTEs, JOINs, CASE bands, window functions
              └─ pandas        row metrics, elasticity, scenario baselines
                  └─ Streamlit + Plotly pages
```

The bundled sample goes through **the same validation** as an upload, so it cannot bypass the rules.

### Validation rules

| Rule | Severity | Action |
|---|---|---|
| Required column missing | fatal | File rejected with the accepted alternative header names |
| Unparseable date | error | Row removed (non-ISO dates are retried as day-first first) |
| Missing required value | error | Row removed |
| Selling or list price ≤ 0 | error | Row removed |
| Unit cost < 0 or units < 0 | error | Row removed |
| Exact duplicate row | error | Removed, first kept |
| Two rows for the same date × product × platform | error | Removed, first kept |
| Non-numeric text in a numeric column | warning | Treated as missing |
| Competitor price ≤ 0 | warning | Set to missing ("not tracked") |
| Negative stock | warning | Set to missing |
| Selling price above list price | warning | Kept; discount shows as negative |
| Selling price below unit cost | warning | Kept; negative gross profit |
| Inconsistent category/brand/name for a product | warning | Standardised to the most frequent value |
| Fractional units | warning | Rounded |

Currency-formatted numbers such as `₹1,299` or `Rs. 450` are parsed. Uploads over 50 MB or 500,000 rows are
refused with a message.

## 2. Metric definitions

All ratios are **ratios of sums** (for example total gross profit ÷ total revenue), never averages of
row-level percentages, and any zero or missing denominator returns blank rather than an error or infinity.

| Metric | Formula |
|---|---|
| Revenue | Σ selling_price × units_sold |
| COGS | Σ unit_cost × units_sold |
| Gross profit | Revenue − COGS |
| Gross margin % | Gross profit ÷ Revenue |
| ASP | Revenue ÷ Units |
| Discount % (row) | (original_price − selling_price) ÷ original_price |
| Effective discount rate | 1 − Revenue ÷ Σ(original_price × units) |
| Discount investment | Σ(original_price − selling_price) × units |
| Competitor gap % (row) | (selling_price − competitor_price) ÷ competitor_price |
| Average competitor gap | Σ(gap % × units) ÷ Σ units, **only** over rows with a competitor price |
| Competitor coverage | Units with a competitor price ÷ all units |
| Price position | Below (< −2 %), parity (±2 %), above (> +2 %) |

**Excluded from profit:** shipping and fulfilment, advertising, marketplace commissions and payment fees,
returns and refunds, taxes (GST/VAT) and operating expenses. Gross margin is therefore an upper bound on
contribution margin.

Every formula is unit-tested in `tests/test_metrics.py`, and `tests/test_sql.py` checks that the SQL
returns the same values as the pandas implementation.

## 3. Price elasticity

**Question:** when a product's price moved, how did its units move?

**Model**, per category:

```
log(units_it) = β · log(price_it) + α_i + γ_t + ε_it
```

- *i* = product × platform series, *t* = week.
- α_i (series fixed effects) removes stable differences between products: quality, brand, typical price, channel.
- γ_t (week fixed effects) removes category-wide shocks such as the festive season.
- β is estimated by OLS after the within transformation; standard errors are clustered by series.

**Why not a simple scatter?** In the sample data promotions are more frequent in the festive season, when
demand is already high. A naive regression credits that seasonal lift to the discount. Across products, it
also mostly measures that expensive items sell fewer units. The app shows the naive slope next to the
fixed-effects estimate so the difference is visible. On the synthetic data the generator's **true**
elasticities are known, and `tests/test_elasticity.py` checks that the fixed-effects estimates recover them
and are closer than the naive slopes.

**Gating:** the analysis is disabled when there is a single date, fewer than 8 periods, or fewer than 5
product/platform series whose log price varies (std ≥ 0.02).

**Remaining confounders and limitations**

- Promotions may coincide with unrecorded ad spend, on-site placement or a product that was already trending.
- Competitor prices are partly tracked and not controlled for in the estimate.
- Stock-outs censor demand; zero-sales weeks are excluded (log of zero).
- Cannibalisation between sibling products and pull-forward (pantry loading) are not modelled.
- Estimates are associations under these assumptions. A randomised price test is required to establish causality.

## 4. Scenario simulator

```
scenario_units = baseline_units × (scenario_price ÷ baseline_price)^elasticity × (1 + other_demand_change)
```

- **Baseline:** the last 8 weeks of the selected scope; units-weighted price and cost, average weekly units.
- **Elasticity default:** the category's fixed-effects estimate when available, otherwise −1.5 (labelled as an
  illustrative assumption). Users can override it.
- **Validation:** prices must be > 0, costs ≥ 0, elasticity between −6 and +1, demand change > −100 %.
- **Warnings:** price below or equal to cost, change beyond ±30 %, price outside the observed range,
  positive elasticity, negative gross profit.
- **Break-even volume:** units needed at the scenario price and cost to keep baseline gross profit.
- **Model optimum:** for elasticity < −1 the constant-elasticity profit maximum is `cost × e ÷ (1 + e)`. It is
  shown as a property of the formula, not a recommendation.
- **Sensitivity table:** the same scenario at both ends of the elasticity's 95 % confidence interval.

Everything is labelled "simulated". Competitor reactions, mix shifts, fees and stock constraints are held
constant, so outputs are not forecasts or guaranteed improvements.
