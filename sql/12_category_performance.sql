-- Category scorecard: JOIN to the product dimension, revenue share via a
-- window SUM over the whole result, and RANK() on gross profit.
WITH filtered AS (
    SELECT f.*, p.category
    FROM fact_sales AS f
    JOIN dim_product AS p ON p.product_id = f.product_id
    WHERE 1 = 1 {{FILTERS}}
),
by_category AS (
    SELECT
        category,
        SUM(selling_price * units_sold)                          AS revenue,
        SUM((selling_price - unit_cost) * units_sold)            AS gross_profit,
        SUM(units_sold)                                          AS units_sold,
        SUM(original_price * units_sold)                         AS list_revenue,
        COUNT(DISTINCT product_id)                               AS products
    FROM filtered
    GROUP BY category
)
SELECT
    category,
    revenue,
    gross_profit,
    gross_profit / NULLIF(revenue, 0)                            AS gross_margin_pct,
    units_sold,
    revenue / NULLIF(units_sold, 0)                              AS avg_selling_price,
    (list_revenue - revenue) / NULLIF(list_revenue, 0)           AS effective_discount_rate,
    products,
    revenue / NULLIF(SUM(revenue) OVER (), 0)                    AS revenue_share,
    gross_profit / NULLIF(SUM(gross_profit) OVER (), 0)          AS gross_profit_share,
    RANK() OVER (ORDER BY gross_profit DESC)                     AS gross_profit_rank
FROM by_category
ORDER BY gross_profit_rank;
