-- ---------------------------------------------------------------------------
-- Star-schema-lite for the pricing analytics database (SQLite).
-- Loaded into an in-memory database at app start from the validated CSV,
-- so no database file is ever committed or deployed.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_sales;
DROP TABLE IF EXISTS dim_product;

CREATE TABLE dim_product (
    product_id    TEXT PRIMARY KEY,
    product_name  TEXT NOT NULL,
    category      TEXT NOT NULL,
    brand         TEXT NOT NULL
);

CREATE TABLE fact_sales (
    date              TEXT    NOT NULL,          -- ISO YYYY-MM-DD (period start)
    product_id        TEXT    NOT NULL REFERENCES dim_product (product_id),
    platform          TEXT    NOT NULL,
    original_price    REAL    NOT NULL CHECK (original_price > 0),
    selling_price     REAL    NOT NULL CHECK (selling_price > 0),
    competitor_price  REAL             CHECK (competitor_price IS NULL OR competitor_price > 0),
    unit_cost         REAL    NOT NULL CHECK (unit_cost >= 0),
    units_sold        INTEGER NOT NULL CHECK (units_sold >= 0),
    stock_on_hand     REAL,
    promo_flag        REAL,
    PRIMARY KEY (date, product_id, platform)
);

CREATE INDEX idx_fact_product  ON fact_sales (product_id);
CREATE INDEX idx_fact_platform ON fact_sales (platform);
CREATE INDEX idx_dim_category  ON dim_product (category);
