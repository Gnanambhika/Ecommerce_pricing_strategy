"""Financial metric definitions.

Every KPI in the app is computed by a function in this module (or by the SQL
in ``sql/`` that is tested to agree with it). All ratios go through
:func:`safe_divide`, so a zero or missing denominator yields ``NaN`` instead of
an exception or a misleading ``inf``.

Scope of "gross profit" in this project
---------------------------------------
Gross profit = revenue - cost of goods sold, where COGS = unit cost x units.
**Excluded**: shipping/fulfilment, advertising, marketplace/payment fees,
returns and refunds, taxes (GST/VAT) and operating expenses. Gross margin is
therefore an upper bound on contribution margin, not net profit.

Percentages are returned as fractions (0.25 == 25 %); formatting happens in
the UI layer.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PARITY_TOLERANCE

Number = int | float
ArrayLike = int | float | np.ndarray | pd.Series


# --------------------------------------------------------------------------
# Primitive, vectorised formulas
# --------------------------------------------------------------------------
def safe_divide(numerator: ArrayLike, denominator: ArrayLike) -> ArrayLike:
    """Divide, returning NaN where the denominator is zero, negative-zero or
    missing. Works on scalars, NumPy arrays and pandas Series (index kept)."""
    if isinstance(numerator, pd.Series) or isinstance(denominator, pd.Series):
        num = numerator
        den = denominator
        if isinstance(num, pd.Series):
            num = pd.to_numeric(num, errors="coerce")
        if isinstance(den, pd.Series):
            den = pd.to_numeric(den, errors="coerce")
        if isinstance(den, pd.Series):
            den = den.where(den != 0)
        elif den is None or pd.isna(den) or den == 0:
            return num * np.nan
        return num / den

    num_arr = np.asarray(numerator, dtype="float64")
    den_arr = np.asarray(denominator, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where((den_arr == 0) | np.isnan(den_arr), np.nan, num_arr / den_arr)
    if out.ndim == 0:
        return float(out)
    return out


def revenue(selling_price: ArrayLike, units_sold: ArrayLike) -> ArrayLike:
    """Revenue = selling price x units sold (net of discounts, before returns)."""
    return selling_price * units_sold


def cost_of_goods_sold(unit_cost: ArrayLike, units_sold: ArrayLike) -> ArrayLike:
    """COGS = unit cost x units sold."""
    return unit_cost * units_sold


def gross_profit(revenue_value: ArrayLike, cogs_value: ArrayLike) -> ArrayLike:
    """Gross profit = revenue - COGS."""
    return revenue_value - cogs_value


def gross_margin_pct(gross_profit_value: ArrayLike, revenue_value: ArrayLike) -> ArrayLike:
    """Gross margin % = gross profit / revenue. NaN when revenue is 0."""
    return safe_divide(gross_profit_value, revenue_value)


def average_selling_price(revenue_value: ArrayLike, units_value: ArrayLike) -> ArrayLike:
    """ASP = revenue / units (a units-weighted mean price). NaN when units are 0."""
    return safe_divide(revenue_value, units_value)


def discount_pct(original_price: ArrayLike, selling_price: ArrayLike) -> ArrayLike:
    """Discount % = (original price - selling price) / original price.

    Negative values mean the item sold *above* its stated list price (flagged by
    validation). NaN when the original price is 0 or missing.
    """
    return safe_divide(original_price - selling_price, original_price)


def competitor_price_gap(selling_price: ArrayLike, competitor_price: ArrayLike) -> ArrayLike:
    """Absolute gap = our selling price - competitor price.

    Positive -> we are more expensive. NaN when the competitor price is missing.
    """
    if competitor_price is None:
        return np.nan
    if isinstance(selling_price, pd.Series) or isinstance(competitor_price, pd.Series):
        sp, cp = selling_price, competitor_price
        if isinstance(sp, pd.Series):
            sp = pd.to_numeric(sp, errors="coerce")
        if isinstance(cp, pd.Series):
            cp = pd.to_numeric(cp, errors="coerce")
        return sp - cp
    result = np.asarray(selling_price, dtype="float64") - np.asarray(competitor_price, dtype="float64")
    return float(result) if result.ndim == 0 else result


def competitor_price_gap_pct(selling_price: ArrayLike, competitor_price: ArrayLike) -> ArrayLike:
    """Relative gap = (our price - competitor price) / competitor price.

    +0.05 means we are 5 % more expensive than the competitor. NaN when the
    competitor price is missing or zero.
    """
    if competitor_price is None:
        return np.nan
    return safe_divide(competitor_price_gap(selling_price, competitor_price), competitor_price)


def price_position(gap_pct: float | None, tolerance: float = PARITY_TOLERANCE) -> str:
    """Classify a relative competitor gap into a position label."""
    if gap_pct is None or pd.isna(gap_pct):
        return "No competitor data"
    if gap_pct < -tolerance:
        return "Below competitor"
    if gap_pct > tolerance:
        return "Above competitor"
    return "At parity"


# --------------------------------------------------------------------------
# DataFrame helpers
# --------------------------------------------------------------------------
def add_row_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of a validated sales frame with per-row derived metrics."""
    out = df.copy()
    out["revenue"] = revenue(out["selling_price"], out["units_sold"])
    out["cogs"] = cost_of_goods_sold(out["unit_cost"], out["units_sold"])
    out["gross_profit"] = gross_profit(out["revenue"], out["cogs"])
    out["gross_margin_pct"] = gross_margin_pct(out["gross_profit"], out["revenue"])
    out["discount_pct"] = discount_pct(out["original_price"], out["selling_price"])
    # Revenue given up versus list price ("discount investment").
    out["discount_amount"] = (out["original_price"] - out["selling_price"]) * out["units_sold"]
    comp = out["competitor_price"] if "competitor_price" in out else pd.Series(np.nan, index=out.index)
    out["competitor_gap"] = competitor_price_gap(out["selling_price"], comp)
    out["competitor_gap_pct"] = competitor_price_gap_pct(out["selling_price"], comp)
    return out


def summarize(df: pd.DataFrame) -> dict[str, float]:
    """Headline KPIs for a (filtered) sales frame.

    ``effective_discount_rate`` is the revenue-weighted discount:
    1 - revenue / list-price revenue. ``avg_competitor_gap_pct`` is the
    units-weighted mean gap, computed **only** over rows where a competitor
    price exists; ``competitor_coverage`` reports what share of units that is.
    """
    empty = {
        "revenue": 0.0, "cogs": 0.0, "gross_profit": 0.0, "gross_margin_pct": np.nan,
        "units_sold": 0.0, "avg_selling_price": np.nan, "effective_discount_rate": np.nan,
        "discount_amount": 0.0, "avg_competitor_gap_pct": np.nan,
        "competitor_coverage": np.nan, "products": 0, "rows": 0,
    }
    if df is None or df.empty:
        return empty

    d = df if "revenue" in df.columns else add_row_metrics(df)
    rev = float(d["revenue"].sum())
    cogs = float(d["cogs"].sum())
    units = float(d["units_sold"].sum())
    list_rev = float((d["original_price"] * d["units_sold"]).sum())
    gp = rev - cogs

    has_comp = d["competitor_gap_pct"].notna()
    comp_units = float(d.loc[has_comp, "units_sold"].sum())
    gap_weighted = safe_divide(
        float((d.loc[has_comp, "competitor_gap_pct"] * d.loc[has_comp, "units_sold"]).sum()),
        comp_units,
    )

    return {
        "revenue": rev,
        "cogs": cogs,
        "gross_profit": gp,
        "gross_margin_pct": safe_divide(gp, rev),
        "units_sold": units,
        "avg_selling_price": safe_divide(rev, units),
        "effective_discount_rate": safe_divide(list_rev - rev, list_rev),
        "discount_amount": float(d["discount_amount"].sum()),
        "avg_competitor_gap_pct": gap_weighted,
        "competitor_coverage": safe_divide(comp_units, units),
        "products": int(d["product_id"].nunique()),
        "rows": int(len(d)),
    }


def rank_entities(
    df: pd.DataFrame,
    by: str,
    metric: str = "gross_profit",
    top_n: int | None = 10,
    ascending: bool = False,
) -> pd.DataFrame:
    """Aggregate to ``by`` (e.g. product_id, category) and rank on ``metric``.

    Ranks use the "min" method (ties share the best rank, like SQL ``RANK()``).
    """
    d = df if "revenue" in df.columns else add_row_metrics(df)
    g = (
        d.groupby(by, dropna=False)
        .agg(revenue=("revenue", "sum"), cogs=("cogs", "sum"), units_sold=("units_sold", "sum"))
        .reset_index()
    )
    g["gross_profit"] = g["revenue"] - g["cogs"]
    g["gross_margin_pct"] = safe_divide(g["gross_profit"], g["revenue"])
    g["avg_selling_price"] = safe_divide(g["revenue"], g["units_sold"])
    g["rank"] = g[metric].rank(method="min", ascending=ascending).astype("Int64")
    g = g.sort_values(["rank", by]).reset_index(drop=True)
    return g.head(top_n) if top_n else g
