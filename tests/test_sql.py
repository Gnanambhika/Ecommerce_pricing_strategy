"""SQL layer: results agree with the pandas metric definitions, window
functions rank correctly, CASE bands are right and filters are parameterised."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from pricing_intel import metrics as m
from pricing_intel.db import QUERY_FILES, Filters, PricingDatabase, build_filter_clause


@pytest.fixture
def db(tiny_clean):
    database = PricingDatabase(tiny_clean)
    yield database
    database.close()


def test_every_query_runs(db):
    for name in QUERY_FILES:
        out = db.query(name)
        assert isinstance(out, pd.DataFrame)


def test_kpis_match_pandas(db, tiny_clean):
    sql = db.query("kpi_summary").iloc[0]
    py = m.summarize(tiny_clean)
    for key in ("revenue", "cogs", "gross_profit", "gross_margin_pct", "units_sold", "avg_selling_price",
                "effective_discount_rate", "avg_competitor_gap_pct", "competitor_coverage"):
        assert sql[key] == pytest.approx(py[key]), key


def test_kpis_match_pandas_on_synthetic_panel(small_panel):
    database = PricingDatabase(small_panel)
    f = Filters(date(2025, 3, 1), date(2025, 9, 30), categories=("Electronics", "Fashion"))
    sql = database.query("kpi_summary", f).iloc[0]
    sub = small_panel[(small_panel["date"] >= "2025-03-01") & (small_panel["date"] <= "2025-09-30")
                      & small_panel["category"].isin(["Electronics", "Fashion"])]
    py = m.summarize(sub)
    for key in ("revenue", "gross_profit", "gross_margin_pct", "avg_competitor_gap_pct"):
        assert sql[key] == pytest.approx(py[key]), key


def test_product_rankings_window_functions(db):
    r = db.query("product_rankings")
    # A: GP = 300 + 200 + 200 = 700; B: 400 + 0 = 400
    assert list(r["product_id"]) == ["A", "B"]
    assert list(r["overall_rank"]) == [1, 2]
    assert list(r["category_rank"]) == [1, 1]  # each is #1 in its own category
    assert r.loc[0, "gross_profit"] == pytest.approx(700)


def test_category_shares_sum_to_one(db):
    c = db.query("category_performance")
    assert c["revenue_share"].sum() == pytest.approx(1)
    assert c["gross_profit_share"].sum() == pytest.approx(1)


def test_monthly_trend_lag(small_panel):
    database = PricingDatabase(small_panel)
    t = database.query("monthly_trend")
    assert pd.isna(t["revenue_mom_growth"].iloc[0])
    assert t["revenue_mom_growth"].iloc[1] == pytest.approx(t["revenue"].iloc[1] / t["revenue"].iloc[0] - 1)


def test_competitor_bands_handle_nulls(db):
    b = db.query("competitor_position").set_index("price_band")
    assert b.loc["No competitor data", "observations"] == 2
    assert b.loc["1. >10% cheaper", "observations"] == 1  # A wk1: -20%
    assert b.loc["3. Parity (±2%)", "observations"] == 1  # B: 0%
    assert b.loc["4. 2-10% pricier", "observations"] == 1  # A wk2: +5.3%
    assert b["unit_share"].sum() == pytest.approx(1)


def test_discount_bands(db):
    b = db.query("discount_bands").set_index("discount_band")
    # discounts: 20%, 10%, 0%, 0%, 20%
    assert b.loc["1. 0-5%", "observations"] == 2
    assert b.loc["2. 5-15%", "observations"] == 1
    assert b.loc["3. 15-25%", "observations"] == 2


def test_pareto_cumulative_share_ends_at_one(small_panel):
    database = PricingDatabase(small_panel)
    p = database.query("profit_pareto")
    assert p["cumulative_share"].iloc[-1] == pytest.approx(1)
    assert p["cumulative_share"].is_monotonic_increasing


def test_filters_restrict_rows(db):
    f = Filters(platforms=("P2",))
    assert db.query("kpi_summary", f).iloc[0]["units_sold"] == 5
    empty = db.query("kpi_summary", Filters(categories=("Nope",))).iloc[0]
    assert pd.isna(empty["revenue"])  # SUM over no rows is NULL, not an error


def test_filter_clause_binds_values_not_sql():
    clause, params = build_filter_clause(Filters(categories=("x'); DROP TABLE fact_sales; --",)))
    assert "DROP" not in clause
    assert params["categories_0"].startswith("x')")


def test_injection_attempt_is_harmless(db):
    db.query("kpi_summary", Filters(brands=("X' OR '1'='1",)))
    assert len(db.execute("SELECT * FROM fact_sales")) == 5
