"""Scenario engine: outputs, baseline equality, validation and warnings."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from pricing_intel.scenario import (
    Baseline,
    ScenarioInputError,
    ScenarioInputs,
    baseline_from_data,
    model_optimal_price,
    profit_curve,
    run_scenario,
    scenario_units,
)

BASE = Baseline(price=100.0, units=1000.0, unit_cost=60.0)


def inputs(**kw):
    params = dict(baseline=BASE, scenario_price=100.0, scenario_unit_cost=60.0, elasticity=-1.5)
    params.update(kw)
    return ScenarioInputs(**params)


def test_no_change_reproduces_baseline():
    r = run_scenario(inputs())
    assert r.scenario["units"] == pytest.approx(1000)
    assert r.scenario["revenue"] == pytest.approx(100_000)
    assert r.scenario["gross_profit"] == pytest.approx(40_000)
    assert r.scenario["gross_margin_pct"] == pytest.approx(0.40)
    assert all(abs(v) < 1e-9 for v in r.change.values())
    assert r.warnings == []


def test_constant_elasticity_math():
    r = run_scenario(inputs(scenario_price=110.0, elasticity=-2.0))
    expected_units = 1000 * (1.1 ** -2.0)
    assert r.scenario["units"] == pytest.approx(expected_units)
    assert r.scenario["revenue"] == pytest.approx(110 * expected_units)
    assert r.scenario["gross_profit"] == pytest.approx((110 - 60) * expected_units)
    assert r.pct_change["units"] == pytest.approx(expected_units / 1000 - 1)


def test_demand_shift_and_cost_change():
    r = run_scenario(inputs(scenario_unit_cost=66.0, demand_shift=0.10))
    assert r.scenario["units"] == pytest.approx(1100)
    assert r.scenario["gross_profit"] == pytest.approx((100 - 66) * 1100)


def test_scenario_units_function():
    assert scenario_units(100, 50, 50, -3.0) == pytest.approx(100)
    assert scenario_units(100, 50, 25, -1.0) == pytest.approx(200)


def test_price_below_cost_warns_and_negative_profit():
    r = run_scenario(inputs(scenario_price=55.0))
    assert any("below unit cost" in w for w in r.warnings)
    assert r.scenario["gross_profit"] < 0
    assert math.isnan(r.break_even_units)


def test_price_equal_cost_warns():
    r = run_scenario(inputs(scenario_price=60.0))
    assert any("equals unit cost" in w for w in r.warnings)


def test_extrapolation_warnings():
    r = run_scenario(inputs(scenario_price=150.0, observed_price_range=(90.0, 110.0)))
    assert any("outside ±" in w for w in r.warnings)
    assert any("outside the range actually observed" in w for w in r.warnings)


def test_positive_elasticity_warns():
    r = run_scenario(inputs(elasticity=0.5, scenario_price=105.0))
    assert any("positive" in w.lower() for w in r.warnings)


@pytest.mark.parametrize("kw", [
    dict(scenario_price=0), dict(scenario_price=-5), dict(scenario_unit_cost=-1),
    dict(elasticity=-10), dict(elasticity=float("nan")), dict(demand_shift=-1.0),
    dict(baseline=Baseline(0, 100, 10)), dict(baseline=Baseline(10, -1, 5)),
    dict(baseline=Baseline(10, 100, -5)),
])
def test_invalid_inputs_raise(kw):
    with pytest.raises(ScenarioInputError):
        run_scenario(inputs(**kw))


def test_break_even_volume():
    # Baseline GP 40,000. At price 90 (margin 30/unit) need 1,333.3 units: +33.3%.
    r = run_scenario(inputs(scenario_price=90.0))
    assert r.break_even_units == pytest.approx(40_000 / 30)
    assert r.break_even_volume_change == pytest.approx(40_000 / 30 / 1000 - 1)


def test_zero_baseline_units_pct_change_is_nan():
    r = run_scenario(inputs(baseline=Baseline(100, 0, 60)))
    assert math.isnan(r.pct_change["units"])


def test_model_optimal_price():
    assert model_optimal_price(60, -2.0) == pytest.approx(120)
    assert math.isnan(model_optimal_price(60, -0.8))
    assert math.isnan(model_optimal_price(0, -2.0))


def test_profit_curve_peaks_at_optimum():
    curve = profit_curve(BASE, 60, -2.0, span=0.5, points=201)
    best = curve.loc[curve["gross_profit"].idxmax(), "price"]
    assert best == pytest.approx(120, rel=0.02)


def test_baseline_from_data_uses_recent_weeks():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-06", "2025-01-13", "2025-01-20", "2025-01-20"]),
        "selling_price": [999, 100, 100, 200],
        "unit_cost": [1, 50, 50, 100],
        "units_sold": [1, 10, 10, 10],
    })
    b = baseline_from_data(df, weeks=2)
    assert b.units == pytest.approx(15)          # 30 units over 2 weeks
    assert b.price == pytest.approx(4000 / 30)   # units-weighted
    assert b.unit_cost == pytest.approx(2000 / 30)


def test_baseline_from_empty_or_zero_units():
    assert baseline_from_data(pd.DataFrame(), 8) is None
    zero = pd.DataFrame({"date": pd.to_datetime(["2025-01-06"]), "selling_price": [10],
                         "unit_cost": [5], "units_sold": [0]})
    assert baseline_from_data(zero, 8) is None
