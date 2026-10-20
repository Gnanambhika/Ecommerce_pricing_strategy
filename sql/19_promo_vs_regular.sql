-- Promotional vs regular weeks, per category.
-- promo_flag is optional in imports; rows without it are reported as 'Unknown'.
WITH filtered AS (
    SELECT f.*, p.category
    FROM fact_sales AS f
    JOIN dim_product AS p ON p.product_id = f.product_id
    WHERE 1 = 1 {{FILTERS}}
)
SELECT
    category,
    CASE WHEN promo_flag = 1 THEN 'Promotion'
         WHEN promo_flag = 0 THEN 'Regular'
         ELSE 'Unknown' END                                   AS week_type,
    COUNT(*)                                                  AS observations,
    AVG(units_sold)                                           AS avg_units_per_week,
    SUM(selling_price * units_sold)                           AS revenue,
    SUM((selling_price - unit_cost) * units_sold)
        / NULLIF(SUM(selling_price * units_sold), 0)          AS gross_margin_pct,
    (SUM(original_price * units_sold) - SUM(selling_price * units_sold))
        / NULLIF(SUM(original_price * units_sold), 0)         AS effective_discount_rate
FROM filtered
GROUP BY category, week_type
ORDER BY category, week_type;
