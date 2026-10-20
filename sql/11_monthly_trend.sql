-- Monthly revenue, gross profit and margin with month-over-month growth
-- (window function LAG).
WITH filtered AS (
    SELECT f.*
    FROM fact_sales AS f
    JOIN dim_product AS p ON p.product_id = f.product_id
    WHERE 1 = 1 {{FILTERS}}
),
monthly AS (
    SELECT
        substr(date, 1, 7) || '-01'                    AS month,
        SUM(selling_price * units_sold)                AS revenue,
        SUM(unit_cost * units_sold)                    AS cogs,
        SUM(units_sold)                                AS units_sold,
        SUM(original_price * units_sold)               AS list_revenue
    FROM filtered
    GROUP BY 1
)
SELECT
    month,
    revenue,
    revenue - cogs                                              AS gross_profit,
    (revenue - cogs) / NULLIF(revenue, 0)                       AS gross_margin_pct,
    units_sold,
    (list_revenue - revenue) / NULLIF(list_revenue, 0)          AS effective_discount_rate,
    revenue / NULLIF(LAG(revenue) OVER (ORDER BY month), 0) - 1 AS revenue_mom_growth
FROM monthly
ORDER BY month;
