# Interview guide

How to present this project in 2, 5 or 15 minutes, and how to answer the questions interviewers usually ask.

## The 30-second pitch

> "I built a pricing and profitability analytics app for an e-commerce catalogue. It answers questions like
> *where does our gross profit come from*, *are we priced above competitors*, *what does discounting cost us*
> and *how sensitive is demand to price*. It's Streamlit on top of SQL and pandas, with a fixed-effects
> elasticity model and a scenario simulator. Because I didn't have access to real retailer data, I wrote a
> reproducible synthetic data generator with known true elasticities, which let me prove the estimation
> method actually recovers the right answer. It has 121 automated tests, including tests that the SQL
> and Python metric definitions agree."

## A 5-minute walkthrough

1. **Executive Overview.** Start with the KPIs and point out the definitions in the tooltips ("gross profit
   excludes fees, shipping, returns and ads; I say so everywhere"). Show the category chart and the observation
   that one category has a high revenue share but a lower profit share.
2. **Pricing & Competitors.** Show the units-weighted gap and explain why rows without a competitor price are
   excluded rather than treated as zero. Then the price-band charts, and read the caption: these are descriptive,
   because cheap weeks coincide with promotions and peak season.
3. **Demand & Elasticity.** This is the analytical core. Show the naive slope (near zero) next to the fixed-effects
   estimate (−0.9 to −2.2) and the generator's true values. Explain *why* they differ.
4. **Scenario Simulator.** Raise price by 10% in a category. Point out the break-even volume line, the sensitivity
   table across the confidence interval, and the "simulated" labelling.
5. **Data Quality.** Upload the messy example and show the validation log catching duplicates, bad dates, invalid
   prices and currency strings.

## Major decisions and how to defend them

**Why synthetic data?**
I wanted a dataset with price variation over time, competitor prices and costs, which public datasets rarely
combine, and I wasn't going to scrape marketplaces against their terms. Synthetic data also gave me ground truth:
I know the real elasticities, so I can test whether my method works. I label it as synthetic on every page and
never present it as market evidence. The import workflow means the same app runs on real data.

**Why SQL *and* pandas?**
SQL for set-based aggregation, ranking and banding, which is what analysts do in a warehouse day to day; pandas for
row-level feature engineering and modelling. I test that both produce the same KPIs, so there is one definition of
"gross margin", not two.

**Why ratio of sums for margin?**
Averaging row-level margins gives a tiny product the same weight as a best-seller. Total gross profit ÷ total
revenue is the number finance would report.

**Why fixed effects for elasticity?**
A plain scatter of price vs units across products mostly says "expensive things sell fewer units", which is not
price sensitivity. Series fixed effects compare each product with itself; week fixed effects remove the festive
season, when promotions *and* demand both rise. In the synthetic data the naive slope is close to zero and
sometimes positive, while the fixed-effects estimates are within about 0.1 of the truth.

**Is it causal?**
No, and I say so in the app. Remaining confounders include ad spend and on-site placement during promotions,
competitor reactions, stock-outs and cannibalisation. To establish causality I'd run a randomised or staggered price
test. The model is useful for sizing and prioritising tests, not for replacing them.

**Why constant elasticity in the simulator?**
It is simple, transparent and matches the log-log estimate. Its weakness is extrapolation, so the app warns beyond
±30% or outside observed prices, shows a confidence-interval sensitivity table and labels outputs as simulations.

**How do you handle bad data?**
Hard failures (missing required columns) stop the import with a clear message listing accepted header names.
Impossible rows (non-positive prices, negative units) are removed and counted. Suspicious-but-possible rows
(price above list, sold below cost) are kept and flagged. Nothing changes silently.

**Security and privacy?**
No secrets or external calls. Uploads stay in memory per session. SQL filters use bound parameters, and a test
confirms an injection string is treated as data. User-supplied text is HTML-escaped before rendering.

**Why Streamlit Community Cloud rather than Vercel?**
Streamlit needs a long-running Python server with websockets; Community Cloud runs exactly that for free with a
GitHub integration. Vercel would require rewriting the front end in Next.js and hosting a Python API separately,
which adds complexity without adding analytical value here.

## Likely follow-up questions

- *"What would you do with real data first?"* Check grain and duplicates, reconcile revenue to finance totals,
  confirm the cost definition, and check price variation per product before trusting any elasticity.
- *"How would you scale it?"* Move SQL to a warehouse (BigQuery/Snowflake/DuckDB), schedule refreshes, cache
  aggregates, and keep the same tested metric layer.
- *"What's the biggest limitation?"* Elasticity without experiments, and gross rather than contribution margin.
- *"What did testing catch?"* My first generator version had a cross-price term that silently changed the own-price
  elasticity, so the recovery test failed (estimate −2.1 vs true −1.5). Fixing the data-generating process, not
  loosening the test, was the right call. I also caught a duplicate-element error in the upload flow during browser
  testing.

## Numbers you can quote (all from the synthetic sample)

Quote these only as properties of the demo data, never as business results:
22,698 rows, 120 products, 6 categories, 3 channels, 78 weeks; competitor price coverage 87.7%;
fixed-effects elasticities between about −1.0 and −2.25, each within about 0.1 of the generator's true value;
121 automated tests.
