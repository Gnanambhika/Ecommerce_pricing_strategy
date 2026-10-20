"""Number formatting for display. NaN-safe: missing values render as an em dash."""

from __future__ import annotations

import math

from ..config import CURRENCY_SYMBOL

DASH = "—"


def _missing(x) -> bool:
    try:
        return x is None or math.isnan(float(x))
    except (TypeError, ValueError):
        return True


def compact_number(x: float, decimals: int = 1) -> str:
    if _missing(x):
        return DASH
    value = float(x)
    sign = "-" if value < 0 else ""
    value = abs(value)
    for threshold, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if value >= threshold:
            return f"{sign}{value / threshold:.{decimals}f}{suffix}"
    return f"{sign}{value:,.0f}"


def currency(x: float, compact: bool = True, decimals: int = 1) -> str:
    if _missing(x):
        return DASH
    value = float(x)
    if compact and abs(value) >= 1e3:
        body = compact_number(abs(value), decimals)
    else:
        body = f"{abs(value):,.0f}"
    return f"{'-' if value < 0 else ''}{CURRENCY_SYMBOL}{body}"


def pct(x: float, decimals: int = 1, signed: bool = False) -> str:
    if _missing(x):
        return DASH
    if abs(float(x)) < 0.5 * 10 ** -(decimals + 2):
        x = 0.0  # avoid "-0.0%"
    return f"{float(x) * 100:+.{decimals}f}%" if signed else f"{float(x) * 100:.{decimals}f}%"


def pp(x: float, decimals: int = 1) -> str:
    """Percentage-point change (for margin deltas)."""
    if _missing(x):
        return DASH
    if abs(float(x)) < 0.5 * 10 ** -(decimals + 2):
        x = 0.0
    return f"{float(x) * 100:+.{decimals}f} pp"


def integer(x: float) -> str:
    if _missing(x):
        return DASH
    return f"{float(x):,.0f}"
