"""Financial formula tests: revenue, COGS, gross profit/margin, ASP, discount,
competitor gap, zero denominators and missing competitor prices."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from pricing_intel import metrics as m


class TestSafeDivide:
    def test_scalar(self):
        assert m.safe_divide(10, 4) == 2.5

    @pytest.mark.parametrize("den", [0, 0.0, -0.0, None, float("nan")])
    def test_zero_or_missing_denominator_is_nan(self, den):
        assert math.isnan(m.safe_divide(10, den))

    def test_array(self):
        out = m.safe_divide(np.array([1, 2, 3]), np.array([1, 0, 3]))
        assert out[0] == 1 and math.isnan(out[1]) and out[2] == 1

    def test_series_keeps_index(self):
        s = m.safe_divide(pd.Series([10, 10], index=["a", "b"]), pd.Series([2, 0], index=["a", "b"]))
        assert list(s.index) == ["a", "b"]
        assert s["a"] == 5 and pd.isna(s["b"])

    def test_series_over_zero_scalar(self):
        assert m.safe_divide(pd.Series([1.0, 2.0]), 0).isna().all()


class TestCoreFormulas:
    def test_revenue_cogs_profit_margin(self):
        rev = m.revenue(80.0, 10)
        cogs = m.cost_of_goods_sold(50.0, 10)
        gp = m.gross_profit(rev, cogs)
        assert (rev, cogs, gp) == (800.0, 500.0, 300.0)
        assert m.gross_margin_pct(gp, rev) == pytest.approx(0.375)

    def test_margin_with_zero_revenue_is_nan(self):
        assert math.isnan(m.gross_margin_pct(0.0, 0.0))

    def test_negative_margin_when_below_cost(self):
        rev, cogs = m.revenue(40, 10), m.cost_of_goods_sold(50, 10)
        assert m.gross_margin_pct(m.gross_profit(rev, cogs), rev) == pytest.approx(-0.25)

    def test_asp_is_units_weighted(self):
        rev = m.revenue(100, 1) + m.revenue(50, 3)
        assert m.average_selling_price(rev, 4) == pytest.approx(62.5)

    def test_asp_zero_units(self):
        assert math.isnan(m.average_selling_price(0, 0))


class TestDiscount:
    def test_discount_pct(self):
        assert m.discount_pct(100.0, 80.0) == pytest.approx(0.20)

    def test_no_discount(self):
        assert m.discount_pct(100.0, 100.0) == 0.0

    def test_above_list_is_negative(self):
        assert m.discount_pct(100.0, 110.0) == pytest.approx(-0.10)

    def test_zero_list_price_is_nan(self):
        assert math.isnan(m.discount_pct(0.0, 10.0))


class TestCompetitorGap:
    def test_gap_and_pct(self):
        assert m.competitor_price_gap(105.0, 100.0) == pytest.approx(5.0)
        assert m.competitor_price_gap_pct(105.0, 100.0) == pytest.approx(0.05)
        assert m.competitor_price_gap_pct(90.0, 100.0) == pytest.approx(-0.10)

    @pytest.mark.parametrize("comp", [None, float("nan"), 0])
    def test_missing_or_zero_competitor_price(self, comp):
        assert math.isnan(m.competitor_price_gap_pct(100.0, comp))

    def test_series_with_nulls(self):
        out = m.competitor_price_gap_pct(pd.Series([110.0, 100.0]), pd.Series([100.0, None]))
        assert out.iloc[0] == pytest.approx(0.10) and pd.isna(out.iloc[1])

    @pytest.mark.parametrize("gap, label", [
        (-0.05, "Below competitor"), (0.0, "At parity"), (0.019, "At parity"),
        (-0.02, "At parity"), (0.05, "Above competitor"), (None, "No competitor data"),
        (float("nan"), "No competitor data"),
    ])
    def test_price_position(self, gap, label):
        assert m.price_position(gap) == label


class TestFrameMetrics:
    def test_add_row_metrics(self, tiny_clean):
        d = m.add_row_metrics(tiny_clean)
        a_p1 = d[(d["product_id"] == "A") & (d["platform"] == "P1") & (d["date"] == "2025-01-06")].iloc[0]
        assert a_p1["revenue"] == 800 and a_p1["cogs"] == 500 and a_p1["gross_profit"] == 300
        assert a_p1["discount_pct"] == pytest.approx(0.2)
        assert a_p1["discount_amount"] == pytest.approx(200)
        assert a_p1["competitor_gap_pct"] == pytest.approx(-0.2)

    def test_summarize_totals(self, tiny_clean):
        s = m.summarize(tiny_clean)
        # revenue: 800 + 450 + 400 + 1000 + 0
        assert s["revenue"] == pytest.approx(2650)
        assert s["cogs"] == pytest.approx(500 + 250 + 200 + 600 + 0)
        assert s["gross_profit"] == pytest.approx(1100)
        assert s["gross_margin_pct"] == pytest.approx(1100 / 2650)
        assert s["units_sold"] == 39
        assert s["avg_selling_price"] == pytest.approx(2650 / 39)
        list_rev = 1000 + 500 + 400 + 1000
        assert s["effective_discount_rate"] == pytest.approx((list_rev - 2650) / list_rev)

    def test_summarize_competitor_gap_ignores_missing(self, tiny_clean):
        s = m.summarize(tiny_clean)
        # rows with competitor price: A/P1 wk1 (-20%, 10u), A/P1 wk2 (+5.26%, 4u), B/P1 (0%, 20u)
        expected = (-0.2 * 10 + (100 / 95 - 1) * 4 + 0 * 20) / 34
        assert s["avg_competitor_gap_pct"] == pytest.approx(expected)
        assert s["competitor_coverage"] == pytest.approx(34 / 39)

    def test_summarize_empty(self):
        s = m.summarize(pd.DataFrame())
        assert s["revenue"] == 0 and math.isnan(s["gross_margin_pct"])

    def test_rank_entities_ties_share_rank(self):
        df = pd.DataFrame({
            "product_id": ["A", "B", "C"], "selling_price": [10, 10, 5], "units_sold": [10, 10, 10],
            "unit_cost": [5, 5, 5], "original_price": [10, 10, 5], "competitor_price": [None] * 3,
        })
        r = m.rank_entities(df, "product_id", top_n=None)
        assert list(r["rank"]) == [1, 1, 3]
        assert r.loc[r["product_id"] == "C", "gross_margin_pct"].iloc[0] == 0
