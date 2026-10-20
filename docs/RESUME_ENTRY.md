# Resume entry

These bullets describe what was built and how. They contain **no invented business impact** (revenue lifted,
hours saved, etc.), because the project runs on synthetic data. If you later apply it to real data, replace or add
bullets with outcomes you can verify.

## Project entry (choose 3–4 bullets)

**E-commerce Pricing Strategy & Profitability Intelligence** | Python, SQL (SQLite), pandas, NumPy, statsmodels, Plotly, Streamlit, pytest
*[GitHub](https://github.com/Gnanambhika/Ecommerce_pricing_strategy) · [Live demo](https://ecommercepricingstrategy-nkk8jbgt8xvtfna7bgdse7.streamlit.app)*

- Built a six-page interactive analytics app covering executive KPIs, competitor price positioning, discount
  profitability, price elasticity and a pricing scenario simulator, with global date, category, brand and channel filters.
- Wrote modular SQL (CTEs, joins to a product dimension, CASE banding, RANK/LAG/running-SUM window functions) on an
  in-memory SQLite star schema, with parameterised filters and tests proving SQL and Python metric definitions agree.
- Estimated category price elasticities with a two-way fixed-effects log-log model (series and week effects,
  clustered errors), and validated the method against a seeded synthetic dataset with known true elasticities,
  recovering each within about 0.1.
- Designed a CSV import pipeline with schema validation, header-alias mapping, currency parsing, duplicate detection,
  invalid-price rules and a data-quality report explaining every removed or repaired row.
- Developed a scenario simulator (price, cost, elasticity, demand shift) with break-even volume, confidence-interval
  sensitivity and guard-rails for below-cost and out-of-range prices, clearly separating simulations from observed results.
- Delivered 121 automated tests (unit, SQL, model-recovery and UI smoke tests), lint checks and a reproducible setup,
  deployed on Streamlit Community Cloud.

## One-line version

Built a Streamlit pricing-analytics app (SQL, pandas, fixed-effects elasticity, scenario simulator) on a documented
synthetic dataset, with 121 tests and a validated CSV import pipeline.

## LinkedIn "Projects" description

Interactive pricing and profitability analytics for an e-commerce catalogue: KPIs, competitor price gaps, discount
economics, price elasticity (two-way fixed effects, validated against known ground truth) and a what-if simulator.
Built with Python, SQL, Plotly and Streamlit; tested with pytest. Uses clearly labelled synthetic data and supports
importing your own CSV.
