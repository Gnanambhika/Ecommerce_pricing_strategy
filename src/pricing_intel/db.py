"""In-memory SQLite access layer.

The validated DataFrame is loaded into a two-table schema
(``dim_product`` + ``fact_sales``, see ``sql/00_schema.sql``) and the
analytics queries in ``sql/`` run against it.

Filters are applied safely: the SQL *structure* of a filter comes only from a
fixed whitelist of columns, and every user-selected *value* is bound as a
named parameter, never interpolated into the SQL text.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import date
from functools import cache

import pandas as pd

from .config import PARITY_TOLERANCE, SQL_DIR

FILTER_TOKEN = "{{FILTERS}}"  # noqa: S105 (placeholder, not a secret)
QUERY_FILES = {
    "kpi_summary": "10_kpi_summary.sql",
    "monthly_trend": "11_monthly_trend.sql",
    "category_performance": "12_category_performance.sql",
    "product_rankings": "13_product_rankings.sql",
    "competitor_position": "14_competitor_position.sql",
    "discount_bands": "15_discount_bands.sql",
    "platform_mix": "16_platform_mix.sql",
    "profit_pareto": "17_profit_pareto.sql",
    "category_platform_gap": "18_category_platform_gap.sql",
    "promo_vs_regular": "19_promo_vs_regular.sql",
}


@dataclass(frozen=True)
class Filters:
    """Global filter selection. Empty tuples mean "no filter" (all values)."""

    start_date: date | None = None
    end_date: date | None = None
    categories: tuple[str, ...] = field(default_factory=tuple)
    brands: tuple[str, ...] = field(default_factory=tuple)
    platforms: tuple[str, ...] = field(default_factory=tuple)


# Column whitelist: filter name -> qualified SQL column.
_LIST_FILTERS = {
    "categories": "p.category",
    "brands": "p.brand",
    "platforms": "f.platform",
}


def build_filter_clause(filters: Filters | None) -> tuple[str, dict]:
    """Return (``AND ...`` SQL fragment, bound parameters) for the filters."""
    params: dict = {"parity": PARITY_TOLERANCE}
    if filters is None:
        return "", params

    parts: list[str] = []
    if filters.start_date is not None:
        parts.append("f.date >= :start_date")
        params["start_date"] = pd.Timestamp(filters.start_date).strftime("%Y-%m-%d")
    if filters.end_date is not None:
        parts.append("f.date <= :end_date")
        params["end_date"] = pd.Timestamp(filters.end_date).strftime("%Y-%m-%d")

    for attr, column in _LIST_FILTERS.items():
        values = getattr(filters, attr)
        if values:
            names = []
            for i, value in enumerate(values):
                key = f"{attr}_{i}"
                params[key] = str(value)
                names.append(f":{key}")
            parts.append(f"{column} IN ({', '.join(names)})")

    clause = "".join(f" AND {p}" for p in parts)
    return clause, params


@cache
def load_sql(name: str) -> str:
    """Read a query from ``sql/`` (by short name or file name)."""
    filename = QUERY_FILES.get(name, name)
    return (SQL_DIR / filename).read_text(encoding="utf-8")


class PricingDatabase:
    """Thread-safe wrapper around one in-memory SQLite connection.

    Streamlit serves each browser session from its own thread, so the shared
    connection is guarded by a lock (queries take milliseconds on this data).
    """

    def __init__(self, df: pd.DataFrame):
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.executescript(load_sql("00_schema.sql"))
        self._load(df)

    def _load(self, df: pd.DataFrame) -> None:
        dim = (
            df[["product_id", "product_name", "category", "brand"]]
            .drop_duplicates(subset="product_id", keep="first")
        )
        fact = df[[
            "date", "product_id", "platform", "original_price", "selling_price",
            "competitor_price", "unit_cost", "units_sold", "stock_on_hand", "promo_flag",
        ]].copy()
        fact["date"] = pd.to_datetime(fact["date"]).dt.strftime("%Y-%m-%d")
        # NaN -> NULL so CHECK constraints and IS NULL logic behave.
        fact = fact.astype(object).where(fact.notna(), None)
        with self._lock:
            dim.to_sql("dim_product", self.conn, if_exists="append", index=False)
            fact.to_sql("fact_sales", self.conn, if_exists="append", index=False)
            self.conn.commit()

    def query(self, name: str, filters: Filters | None = None) -> pd.DataFrame:
        """Run a named query from ``sql/`` with the given filters."""
        sql = load_sql(name)
        clause, params = build_filter_clause(filters)
        sql = sql.replace(FILTER_TOKEN, clause)
        with self._lock:
            return pd.read_sql_query(sql, self.conn, params=params)

    def execute(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        """Run ad-hoc read-only SQL (used by tests and the methodology page)."""
        with self._lock:
            return pd.read_sql_query(sql, self.conn, params=params or {})

    def close(self) -> None:
        with self._lock:
            self.conn.close()
