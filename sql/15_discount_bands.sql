-- Discount depth bands vs volume and margin (CASE + aggregate).
WITH filtered AS (
    SELECT f.*,
           (f.original_price - f.selling_price) / f.original_price AS discount_pct
    FROM fact_sales AS f
    JOIN dim_product AS p ON p.product_id = f.product_id
    WHERE 1 = 1 {{FILTERS}}
),
banded AS (
    SELECT
        *,
        CASE
            WHEN discount_pct <  0.05 THEN '1. 0-5%'
            WHEN discount_pct <  0.15 THEN '2. 5-15%'
            WHEN discount_pct <  0.25 THEN '3. 15-25%'
            WHEN discount_pct <  0.35 THEN '4. 25-35%'
            ELSE '5. 35%+'
        END AS discount_band
    FROM filtered
)
SELECT
    discount_band,
    COUNT(*)                                                    AS observations,
    AVG(units_sold)                                             AS avg_units_per_week,
    SUM(units_sold)                                             AS units_sold,
    SUM(selling_price * units_sold)                             AS revenue,
    SUM((selling_price - unit_cost) * units_sold)               AS gross_profit,
    SUM((selling_price - unit_cost) * units_sold)
        / NULLIF(SUM(selling_price * units_sold), 0)            AS gross_margin_pct,
    SUM((original_price - selling_price) * units_sold)          AS discount_amount
FROM banded
GROUP BY discount_band
ORDER BY discount_band;
