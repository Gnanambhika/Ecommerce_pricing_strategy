-- Performance by competitive price position (CASE banding of the gap).
-- Rows without a competitor price form their own band, never a zero gap.
WITH filtered AS (
    SELECT f.*
    FROM fact_sales AS f
    JOIN dim_product AS p ON p.product_id = f.product_id
    WHERE 1 = 1 {{FILTERS}}
),
banded AS (
    SELECT
        *,
        CASE
            WHEN competitor_price IS NULL THEN 'No competitor data'
            WHEN (selling_price - competitor_price) / competitor_price < -0.10 THEN '1. >10% cheaper'
            WHEN (selling_price - competitor_price) / competitor_price < -:parity THEN '2. 2-10% cheaper'
            WHEN (selling_price - competitor_price) / competitor_price <=  :parity THEN '3. Parity (±2%)'
            WHEN (selling_price - competitor_price) / competitor_price <=  0.10 THEN '4. 2-10% pricier'
            ELSE '5. >10% pricier'
        END AS price_band
    FROM filtered
)
SELECT
    price_band,
    COUNT(*)                                                     AS observations,
    SUM(units_sold)                                              AS units_sold,
    AVG(units_sold)                                              AS avg_units_per_week,
    SUM(selling_price * units_sold)                              AS revenue,
    SUM((selling_price - unit_cost) * units_sold)
        / NULLIF(SUM(selling_price * units_sold), 0)             AS gross_margin_pct,
    CAST(SUM(units_sold) AS REAL) / NULLIF(SUM(SUM(units_sold)) OVER (), 0) AS unit_share
FROM banded
GROUP BY price_band
ORDER BY price_band;
