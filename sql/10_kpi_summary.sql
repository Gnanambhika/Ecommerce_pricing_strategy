-- Headline KPIs for the current filter selection.
-- Ratios use NULLIF so a zero denominator returns NULL instead of an error.
WITH filtered AS (
    SELECT f.*, p.category, p.brand
    FROM fact_sales AS f
    JOIN dim_product AS p ON p.product_id = f.product_id
    WHERE 1 = 1 {{FILTERS}}
),
totals AS (
    SELECT
        SUM(selling_price * units_sold)                         AS revenue,
        SUM(unit_cost * units_sold)                             AS cogs,
        SUM(units_sold)                                         AS units_sold,
        SUM(original_price * units_sold)                        AS list_revenue,
        SUM(CASE WHEN competitor_price IS NOT NULL
                 THEN units_sold END)                           AS comp_units,
        SUM(CASE WHEN competitor_price IS NOT NULL
                 THEN (selling_price - competitor_price) / competitor_price * units_sold
            END)                                                AS comp_gap_weighted,
        COUNT(DISTINCT product_id)                              AS products
    FROM filtered
)
SELECT
    revenue,
    cogs,
    revenue - cogs                                              AS gross_profit,
    (revenue - cogs) / NULLIF(revenue, 0)                       AS gross_margin_pct,
    units_sold,
    revenue / NULLIF(units_sold, 0)                             AS avg_selling_price,
    (list_revenue - revenue) / NULLIF(list_revenue, 0)          AS effective_discount_rate,
    comp_gap_weighted / NULLIF(comp_units, 0)                   AS avg_competitor_gap_pct,
    CAST(comp_units AS REAL) / NULLIF(units_sold, 0)            AS competitor_coverage,
    products
FROM totals;
