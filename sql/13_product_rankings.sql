-- Product leaderboard with an overall rank and a rank *within* each category
-- (RANK ... PARTITION BY).
WITH filtered AS (
    SELECT f.*, p.product_name, p.category, p.brand
    FROM fact_sales AS f
    JOIN dim_product AS p ON p.product_id = f.product_id
    WHERE 1 = 1 {{FILTERS}}
),
by_product AS (
    SELECT
        product_id,
        product_name,
        category,
        brand,
        SUM(selling_price * units_sold)                   AS revenue,
        SUM((selling_price - unit_cost) * units_sold)     AS gross_profit,
        SUM(units_sold)                                   AS units_sold,
        SUM(original_price * units_sold)                  AS list_revenue
    FROM filtered
    GROUP BY product_id, product_name, category, brand
)
SELECT
    product_id,
    product_name,
    category,
    brand,
    revenue,
    gross_profit,
    gross_profit / NULLIF(revenue, 0)                                  AS gross_margin_pct,
    units_sold,
    revenue / NULLIF(units_sold, 0)                                    AS avg_selling_price,
    (list_revenue - revenue) / NULLIF(list_revenue, 0)                 AS effective_discount_rate,
    RANK() OVER (ORDER BY gross_profit DESC)                           AS overall_rank,
    RANK() OVER (PARTITION BY category ORDER BY gross_profit DESC)     AS category_rank
FROM by_product
ORDER BY overall_rank, product_id;
