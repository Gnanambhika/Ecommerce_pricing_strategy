-- Units-weighted competitor price gap for every category x platform cell.
WITH filtered AS (
    SELECT f.*, p.category
    FROM fact_sales AS f
    JOIN dim_product AS p ON p.product_id = f.product_id
    WHERE f.competitor_price IS NOT NULL {{FILTERS}}
)
SELECT
    category,
    platform,
    SUM((selling_price - competitor_price) / competitor_price * units_sold)
        / NULLIF(SUM(units_sold), 0)                     AS avg_gap_pct,
    COUNT(*)                                             AS observations
FROM filtered
GROUP BY category, platform
ORDER BY category, platform;
