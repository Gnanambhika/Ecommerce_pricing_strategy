"""Own-price elasticity estimation.

Method
------
For each category we fit a log-log regression with **two-way fixed effects**:

    log(units_it) = beta * log(price_it) + alpha_i + gamma_t + e_it

* ``i`` is a product x platform series, ``t`` a week.
* ``alpha_i`` absorbs everything constant about a series (its quality, brand,
  typical price level, channel), so ``beta`` is identified only from a series'
  price moving *relative to its own normal level*.
* ``gamma_t`` absorbs anything that hits the whole category in a given week
  (festive season, paydays, site-wide events), so the seasonal lift that
  coincides with promotions is not credited to price.
* Standard errors are clustered by series (errors are correlated over time
  within a product).

``beta`` is the elasticity: a 1 % price increase is *associated with* a
``beta`` % change in units, holding the fixed effects constant.

Limitations (shown in the app): rows with zero units are dropped (log), stock-
outs censor demand, competitor moves, advertising and on-site placement are not
controlled, and promotions may be timed when a product is already trending.
These are associations under stated assumptions, not proof of causation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .config import (
    MIN_PERIODS_FOR_ELASTICITY,
    MIN_PRICE_VARIATION,
    MIN_SERIES_WITH_VARIATION,
)

MIN_OBS_PER_GROUP = 60


@dataclass
class Feasibility:
    ok: bool
    reasons: list[str]
    periods: int
    series: int
    series_with_variation: int


def _series_id(df: pd.DataFrame) -> pd.Series:
    return df["product_id"].astype(str) + " | " + df["platform"].astype(str)


def check_feasibility(df: pd.DataFrame) -> Feasibility:
    """Is there enough price variation over time to estimate elasticity?

    A single price snapshot (one period) or prices that never change make
    elasticity unidentifiable; the app disables the analysis in that case.
    """
    reasons: list[str] = []
    if df is None or df.empty:
        return Feasibility(False, ["No data in the current selection."], 0, 0, 0)

    periods = int(df["date"].nunique())
    work = df[(df["selling_price"] > 0)].assign(series=_series_id, log_p=lambda d: np.log(d["selling_price"]))
    variation = work.groupby("series")["log_p"].std().fillna(0.0)
    n_var = int((variation >= MIN_PRICE_VARIATION).sum())

    if periods < 2:
        reasons.append("Only a single price snapshot is available. Elasticity needs prices observed over time.")
    elif periods < MIN_PERIODS_FOR_ELASTICITY:
        reasons.append(f"Only {periods} periods are available; at least {MIN_PERIODS_FOR_ELASTICITY} are needed.")
    if n_var < MIN_SERIES_WITH_VARIATION:
        reasons.append(
            f"Only {n_var} product/platform series show meaningful price changes "
            f"(need {MIN_SERIES_WITH_VARIATION})."
        )
    return Feasibility(not reasons, reasons, periods, int(variation.size), n_var)


def prepare_panel(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Log-transform and keep estimable rows. Returns (panel, zero_rows_dropped)."""
    work = df[(df["selling_price"] > 0)].copy()
    zero_rows = int((work["units_sold"] <= 0).sum())
    work = work[work["units_sold"] > 0]
    work["series"] = _series_id(work)
    work["period"] = pd.to_datetime(work["date"]).dt.strftime("%Y-%m-%d")
    work["log_q"] = np.log(work["units_sold"].astype(float))
    work["log_p"] = np.log(work["selling_price"].astype(float))
    return work, zero_rows


def _fit_two_way(panel: pd.DataFrame) -> dict:
    """Within-transform by series, then OLS with period dummies (FWL)."""
    y = panel["log_q"] - panel.groupby("series")["log_q"].transform("mean")
    x_price = panel["log_p"] - panel.groupby("series")["log_p"].transform("mean")

    periods = pd.get_dummies(panel["period"], drop_first=True, dtype=float)
    periods_dm = periods - periods.groupby(panel["series"]).transform("mean")

    X = pd.concat([x_price.rename("log_p"), periods_dm], axis=1)
    model = sm.OLS(y.to_numpy(), X.to_numpy())
    groups = pd.factorize(panel["series"])[0]
    res = model.fit(cov_type="cluster", cov_kwds={"groups": groups})
    beta = float(res.params[0])
    se = float(res.bse[0])
    ci_low, ci_high = (float(v) for v in res.conf_int()[0])
    within_r2 = float(1 - np.sum(res.resid ** 2) / np.sum((y - y.mean()) ** 2)) if len(y) > 1 else np.nan
    return {
        "elasticity": beta,
        "std_error": se,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "p_value": float(res.pvalues[0]),
        "within_r2": within_r2,
    }


def _fit_naive(panel: pd.DataFrame) -> float:
    """Pooled log-log slope with no controls: correlation only, shown for contrast."""
    x = panel["log_p"].to_numpy()
    y = panel["log_q"].to_numpy()
    if np.std(x) == 0:
        return np.nan
    return float(np.polyfit(x, y, 1)[0])


def interpret(elasticity: float, ci_low: float, ci_high: float) -> str:
    """Plain-language reading of an estimate and its 95 % interval."""
    if any(pd.isna(v) for v in (elasticity, ci_low, ci_high)):
        return "Not estimated"
    if ci_low > 0:
        return "Positive (likely confounded; do not use)"
    if ci_high < -1:
        return "Elastic: units moved more than proportionally with price"
    if ci_low > -1 and ci_high < 0:
        return "Inelastic: units moved less than proportionally with price"
    if ci_high >= 0:
        return "Not distinguishable from zero"
    return "Not distinguishable from unit elasticity (-1)"


def estimate_elasticities(df: pd.DataFrame, group_col: str = "category") -> pd.DataFrame:
    """Estimate elasticity per group (default: category) plus an 'All' pooled row."""
    columns = ["group", "elasticity", "std_error", "ci_low", "ci_high", "p_value", "within_r2",
               "naive_elasticity", "n_obs", "n_series", "zero_rows_dropped", "interpretation", "note"]
    if df is None or df.empty:
        return pd.DataFrame(columns=columns)

    rows = []
    groups = [(g, sub) for g, sub in df.groupby(group_col)] + [("All (pooled)", df)]
    for name, sub in groups:
        panel, zero_rows = prepare_panel(sub)
        base = {"group": name, "n_obs": len(panel), "n_series": panel["series"].nunique() if len(panel) else 0,
                "zero_rows_dropped": zero_rows}
        variation = panel.groupby("series")["log_p"].std().fillna(0) if len(panel) else pd.Series(dtype=float)
        if len(panel) < MIN_OBS_PER_GROUP or (variation >= MIN_PRICE_VARIATION).sum() < 3:
            rows.append({**base, "interpretation": "Not estimated",
                         "note": "Too few observations or too little price variation."})
            continue
        fit = _fit_two_way(panel)
        rows.append({
            **base, **fit,
            "naive_elasticity": _fit_naive(panel),
            "interpretation": interpret(fit["elasticity"], fit["ci_low"], fit["ci_high"]),
            "note": "",
        })
    return pd.DataFrame(rows).reindex(columns=columns)


def binned_relationship(df: pd.DataFrame, bins: int = 20) -> pd.DataFrame:
    """Binned scatter of price vs units after removing series and week means.

    Each point is the mean of ~1/bins of observations, ordered by their price
    deviation. Approximate two-way demeaning (exact for balanced panels); used
    for visual intuition only. The regression above is the estimate.
    """
    panel, _ = prepare_panel(df)
    if len(panel) < bins * 5:
        return pd.DataFrame(columns=["price_dev_pct", "units_dev_pct", "n"])
    grand_q, grand_p = panel["log_q"].mean(), panel["log_p"].mean()
    for col, grand in (("log_q", grand_q), ("log_p", grand_p)):
        panel[f"{col}_dm"] = (panel[col]
                              - panel.groupby("series")[col].transform("mean")
                              - panel.groupby("period")[col].transform("mean")
                              + grand)
    panel["bin"] = pd.qcut(panel["log_p_dm"].rank(method="first"), q=bins, labels=False)
    out = panel.groupby("bin").agg(x=("log_p_dm", "mean"), y=("log_q_dm", "mean"), n=("log_q", "size"))
    out["price_dev_pct"] = np.expm1(out["x"]) * 100
    out["units_dev_pct"] = np.expm1(out["y"]) * 100
    return out[["price_dev_pct", "units_dev_pct", "n"]].reset_index(drop=True)
