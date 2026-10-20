"""Pricing scenario engine.

Model (constant elasticity, everything else held equal):

    scenario_units = baseline_units
                     x (scenario_price / baseline_price) ** elasticity
                     x (1 + demand_shift)

``demand_shift`` lets the user add an assumed change in demand that is *not*
caused by price (e.g. seasonality or a marketing push). Results are model
outputs under these assumptions, not forecasts or guaranteed outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import EXTRAPOLATION_LIMIT
from .metrics import safe_divide

ELASTICITY_BOUNDS = (-6.0, 1.0)


class ScenarioInputError(ValueError):
    """Raised for inputs the model cannot evaluate."""


@dataclass(frozen=True)
class Baseline:
    price: float
    units: float
    unit_cost: float

    @property
    def revenue(self) -> float:
        return self.price * self.units

    @property
    def gross_profit(self) -> float:
        return (self.price - self.unit_cost) * self.units


@dataclass(frozen=True)
class ScenarioInputs:
    baseline: Baseline
    scenario_price: float
    scenario_unit_cost: float
    elasticity: float
    demand_shift: float = 0.0  # fraction, e.g. 0.05 = +5 %
    observed_price_range: tuple[float, float] | None = None


@dataclass
class ScenarioResult:
    baseline: dict
    scenario: dict
    change: dict
    pct_change: dict
    warnings: list[str] = field(default_factory=list)
    break_even_units: float = float("nan")
    break_even_volume_change: float = float("nan")


def validate_inputs(inputs: ScenarioInputs) -> list[str]:
    """Raise for impossible inputs; return warnings for risky-but-valid ones."""
    b = inputs.baseline
    if not np.isfinite(b.price) or b.price <= 0:
        raise ScenarioInputError("Baseline price must be greater than zero.")
    if not np.isfinite(b.units) or b.units < 0:
        raise ScenarioInputError("Baseline units cannot be negative.")
    if not np.isfinite(b.unit_cost) or b.unit_cost < 0:
        raise ScenarioInputError("Baseline unit cost cannot be negative.")
    if not np.isfinite(inputs.scenario_price) or inputs.scenario_price <= 0:
        raise ScenarioInputError("Scenario price must be greater than zero.")
    if not np.isfinite(inputs.scenario_unit_cost) or inputs.scenario_unit_cost < 0:
        raise ScenarioInputError("Scenario unit cost cannot be negative.")
    lo, hi = ELASTICITY_BOUNDS
    if not np.isfinite(inputs.elasticity) or not lo <= inputs.elasticity <= hi:
        raise ScenarioInputError(f"Elasticity must be between {lo} and {hi}.")
    if not np.isfinite(inputs.demand_shift) or inputs.demand_shift <= -1:
        raise ScenarioInputError("Demand shift must be greater than -100%.")

    warnings: list[str] = []
    if inputs.scenario_price < inputs.scenario_unit_cost:
        warnings.append("Scenario price is below unit cost: every unit sold loses money.")
    elif inputs.scenario_price == inputs.scenario_unit_cost:
        warnings.append("Scenario price equals unit cost: gross profit is zero.")
    change = inputs.scenario_price / b.price - 1
    if abs(change) > EXTRAPOLATION_LIMIT:
        warnings.append(
            f"Price change of {change:+.0%} is outside ±{EXTRAPOLATION_LIMIT:.0%}. A constant-"
            "elasticity model is unreliable far from observed prices."
        )
    if inputs.observed_price_range is not None:
        lo_obs, hi_obs = inputs.observed_price_range
        if not lo_obs <= inputs.scenario_price <= hi_obs:
            warnings.append(
                "Scenario price is outside the range actually observed in the data; "
                "the estimate is an extrapolation."
            )
    if inputs.elasticity > 0:
        warnings.append("Elasticity is positive (demand rises with price). This usually signals "
                        "confounding; treat results with caution.")
    return warnings


def scenario_units(baseline_units: float, baseline_price: float, scenario_price: float,
                   elasticity: float, demand_shift: float = 0.0) -> float:
    """Constant-elasticity demand response."""
    return float(baseline_units * (scenario_price / baseline_price) ** elasticity * (1 + demand_shift))


def _metrics(price: float, units: float, unit_cost: float) -> dict:
    revenue = price * units
    cogs = unit_cost * units
    gp = revenue - cogs
    return {
        "price": price,
        "units": units,
        "unit_cost": unit_cost,
        "revenue": revenue,
        "cogs": cogs,
        "gross_profit": gp,
        "gross_margin_pct": safe_divide(gp, revenue),
    }


def run_scenario(inputs: ScenarioInputs) -> ScenarioResult:
    """Evaluate one scenario against its baseline."""
    warnings = validate_inputs(inputs)
    b = inputs.baseline
    units = scenario_units(b.units, b.price, inputs.scenario_price, inputs.elasticity, inputs.demand_shift)

    base = _metrics(b.price, b.units, b.unit_cost)
    scen = _metrics(inputs.scenario_price, units, inputs.scenario_unit_cost)
    keys = ["price", "units", "unit_cost", "revenue", "cogs", "gross_profit"]
    change = {k: scen[k] - base[k] for k in keys}
    change["gross_margin_pct"] = scen["gross_margin_pct"] - base["gross_margin_pct"]
    pct = {k: safe_divide(scen[k] - base[k], abs(base[k])) for k in keys}

    unit_margin = inputs.scenario_price - inputs.scenario_unit_cost
    break_even_units = safe_divide(base["gross_profit"], unit_margin) if unit_margin > 0 else float("nan")
    break_even_change = safe_divide(break_even_units - b.units, b.units) \
        if np.isfinite(break_even_units) else float("nan")

    if scen["gross_profit"] < 0:
        warnings.append("Scenario gross profit is negative.")

    return ScenarioResult(base, scen, change, pct, warnings, float(break_even_units), float(break_even_change))


def profit_curve(baseline: Baseline, unit_cost: float, elasticity: float,
                 demand_shift: float = 0.0, span: float = 0.4, points: int = 81) -> pd.DataFrame:
    """Revenue and gross profit across a price grid around the baseline price."""
    prices = np.linspace(baseline.price * (1 - span), baseline.price * (1 + span), points)
    units = baseline.units * (prices / baseline.price) ** elasticity * (1 + demand_shift)
    return pd.DataFrame({
        "price": prices,
        "units": units,
        "revenue": prices * units,
        "gross_profit": (prices - unit_cost) * units,
        "price_change_pct": prices / baseline.price - 1,
    })


def model_optimal_price(unit_cost: float, elasticity: float) -> float:
    """Profit-maximising price under constant elasticity: c * e / (1 + e).

    Defined only for elastic demand (e < -1). For e >= -1 the model implies
    profit keeps rising with price, which is a sign the model has left its
    valid range, so NaN is returned.
    """
    if elasticity >= -1 or unit_cost <= 0:
        return float("nan")
    return float(unit_cost * elasticity / (1 + elasticity))


def baseline_from_data(df: pd.DataFrame, weeks: int) -> Baseline | None:
    """Observed baseline from the most recent ``weeks`` periods of a slice:
    units-weighted price and cost, and average weekly units."""
    if df is None or df.empty:
        return None
    dates = pd.to_datetime(df["date"])
    recent_dates = sorted(dates.unique())[-weeks:]
    recent = df[dates.isin(recent_dates)]
    units = float(recent["units_sold"].sum())
    if units <= 0:
        return None
    price = float((recent["selling_price"] * recent["units_sold"]).sum() / units)
    cost = float((recent["unit_cost"] * recent["units_sold"]).sum() / units)
    weekly_units = units / len(recent_dates)
    return Baseline(price=price, units=weekly_units, unit_cost=cost)
