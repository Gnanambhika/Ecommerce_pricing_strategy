-- Channel comparison with each platform's share of revenue.
WITH filtered AS (
    SELECT f.*
    FROM fact_sales AS f
    JOIN dim_product AS p ON p.product_id = f.product_id
    WHERE 1 = 1 {{FILTERS}}
)
SELECT
    platform,
    SUM(selling_price * units_sold)                                  AS revenue,
    SUM((selling_price - unit_cost) * units_sold)                    AS gross_profit,
    SUM((selling_price - unit_cost) * units_sold)
        / NULLIF(SUM(selling_price * units_sold), 0)                 AS gross_margin_pct,
    SUM(units_sold)                                                  AS units_sold,
    SUM(selling_price * units_sold) / NULLIF(SUM(units_sold), 0)     AS avg_selling_price,
    SUM(selling_price * units_sold)
        / NULLIF(SUM(SUM(selling_price * units_sold)) OVER (), 0)    AS revenue_share
FROM filtered
GROUP BY platform
ORDER BY revenue DESC;
