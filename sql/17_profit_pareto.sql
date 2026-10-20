-- Gross-profit concentration (Pareto): running share of total gross profit
-- by product, using a cumulative window SUM.
WITH filtered AS (
    SELECT f.*, p.product_name, p.category
    FROM fact_sales AS f
    JOIN dim_product AS p ON p.product_id = f.product_id
    WHERE 1 = 1 {{FILTERS}}
),
by_product AS (
    SELECT product_id, product_name, category,
           SUM((selling_price - unit_cost) * units_sold) AS gross_profit
    FROM filtered
    GROUP BY product_id, product_name, category
)
SELECT
    product_id,
    product_name,
    category,
    gross_profit,
    ROW_NUMBER() OVER (ORDER BY gross_profit DESC, product_id)              AS product_rank,
    SUM(gross_profit) OVER (ORDER BY gross_profit DESC, product_id
                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        / NULLIF(SUM(gross_profit) OVER (), 0)                              AS cumulative_share,
    CAST(ROW_NUMBER() OVER (ORDER BY gross_profit DESC, product_id) AS REAL)
        / COUNT(*) OVER ()                                                  AS product_share
FROM by_product
ORDER BY product_rank;
