"""Elasticity: feasibility gating, recovery of known true values, robustness."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pricing_intel.data_generation import TRUE_ELASTICITY
from pricing_intel.elasticity import (
    binned_relationship,
    check_feasibility,
    estimate_elasticities,
    interpret,
)


def test_single_snapshot_is_not_feasible(small_panel):
    one_week = small_panel[small_panel["date"] == small_panel["date"].min()]
    feas = check_feasibility(one_week)
    assert not feas.ok
    assert any("single price snapshot" in r for r in feas.reasons)


def test_constant_prices_are_not_feasible(small_panel):
    flat = small_panel.copy()
    flat["selling_price"] = flat.groupby(["product_id", "platform"])["selling_price"].transform("mean")
    assert not check_feasibility(flat).ok


def test_empty_is_not_feasible():
    assert not check_feasibility(pd.DataFrame()).ok


def test_synthetic_panel_is_feasible(small_panel):
    assert check_feasibility(small_panel).ok


def test_recovers_true_elasticities(small_panel):
    est = estimate_elasticities(small_panel).set_index("group")
    for category, truth in TRUE_ELASTICITY.items():
        row = est.loc[category]
        # Within 0.45 of truth (small test panel, censoring and competitor effects add noise).
        assert abs(row["elasticity"] - truth) < 0.45, (category, row["elasticity"], truth)
    assert est.loc["All (pooled)", "n_obs"] == est.drop("All (pooled)")["n_obs"].sum()


def test_fixed_effects_beat_naive_slope(small_panel):
    est = estimate_elasticities(small_panel).set_index("group").drop("All (pooled)")
    truth = est.index.map(TRUE_ELASTICITY)
    fe_error = np.abs(est["elasticity"] - truth).mean()
    naive_error = np.abs(est["naive_elasticity"] - truth).mean()
    assert fe_error < naive_error


def test_zero_unit_rows_are_dropped_and_counted(small_panel):
    d = small_panel.copy()
    d.loc[d.index[:25], "units_sold"] = 0
    est = estimate_elasticities(d)
    assert est["zero_rows_dropped"].sum() >= 25


def test_small_group_not_estimated(small_panel):
    tiny = small_panel[small_panel["product_id"] == small_panel["product_id"].iloc[0]].head(10)
    est = estimate_elasticities(tiny)
    assert est["elasticity"].isna().all()
    assert (est["interpretation"] == "Not estimated").all()


@pytest.mark.parametrize("e, lo, hi, expected", [
    (-2.0, -2.5, -1.5, "Elastic"), (-0.5, -0.8, -0.2, "Inelastic"), (0.5, 0.2, 0.8, "Positive"),
    (-0.9, -1.3, -0.5, "unit elasticity"), (-0.2, -0.6, 0.2, "zero"),
])
def test_interpretation(e, lo, hi, expected):
    assert expected.lower() in interpret(e, lo, hi).lower()


def test_binned_relationship_slopes_down(small_panel):
    b = binned_relationship(small_panel[small_panel["category"] == "Fashion"], bins=10)
    assert len(b) == 10
    assert np.corrcoef(b["price_dev_pct"], b["units_dev_pct"])[0, 1] < -0.8
