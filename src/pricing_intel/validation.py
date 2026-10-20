"""Schema validation and cleaning for imported sales CSVs.

Pipeline (each step logs an :class:`Issue` so the Data Quality page can explain
exactly what happened to the user's file):

1. Normalise headers and map common aliases (``MRP`` -> ``original_price``).
2. Fail fast with a clear message if required columns are missing.
3. Parse numbers (tolerating ``₹1,299``-style strings) and dates.
4. Drop rows missing required values or with impossible values
   (non-positive prices, negative cost or units).
5. Repair-and-flag softer problems (zero competitor price -> missing,
   price above list, sold below cost).
6. Remove exact duplicates, then duplicates on the business key
   ``(date, product_id, platform)`` keeping the first occurrence.

Rows are never silently changed: every drop or repair is counted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import MAX_UPLOAD_ROWS
from .schema import (
    ALL_COLUMNS,
    COLUMN_ALIASES,
    KEY_COLUMNS,
    NUMERIC_COLUMNS,
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
)

STRING_COLUMNS = ("product_id", "product_name", "category", "brand", "platform")
_CURRENCY_RE = re.compile(r"(?i)(₹|\$|€|£|\brs\.?|\binr\b|,|\s)")
_TRUE_VALUES = {"1", "true", "yes", "y", "t"}
_FALSE_VALUES = {"0", "false", "no", "n", "f"}


class ValidationError(ValueError):
    """Raised when a file cannot be used at all (e.g. missing required columns)."""


@dataclass
class Issue:
    check: str
    severity: str  # "error" (rows removed) | "warning" (kept or repaired) | "info"
    rows: int
    action: str
    detail: str = ""


@dataclass
class ValidationResult:
    data: pd.DataFrame
    issues: list[Issue] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    @property
    def issues_frame(self) -> pd.DataFrame:
        cols = ["check", "severity", "rows", "action", "detail"]
        if not self.issues:
            return pd.DataFrame(columns=cols)
        return pd.DataFrame([i.__dict__ for i in self.issues])[cols]

    @property
    def rows_removed(self) -> int:
        return int(self.summary.get("rows_in", 0) - self.summary.get("rows_out", 0))


def normalize_header(name: str) -> str:
    """'  Sale Price ' -> 'sale_price' (also strips a UTF-8 BOM)."""
    cleaned = str(name).replace("﻿", "").strip().lower()
    cleaned = re.sub(r"[\s\-./]+", "_", cleaned)
    return re.sub(r"_+", "_", cleaned).strip("_")


def parse_numeric(series: pd.Series) -> pd.Series:
    """Parse numbers, tolerating currency symbols and thousands separators."""
    if pd.api.types.is_numeric_dtype(series):
        return series.astype("float64")
    as_text = series.astype("string").str.replace(_CURRENCY_RE, "", regex=True)
    as_text = as_text.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "<NA>": pd.NA})
    return pd.to_numeric(as_text, errors="coerce").astype("float64")


def _parse_bool(series: pd.Series) -> pd.Series:
    text = series.astype("string").str.strip().str.lower()
    out = pd.Series(np.nan, index=series.index, dtype="float64")
    out[text.isin(_TRUE_VALUES)] = 1.0
    out[text.isin(_FALSE_VALUES)] = 0.0
    return out


def _parse_dates(series: pd.Series) -> tuple[pd.Series, int]:
    """ISO dates first; anything else is retried day-first (common in India/EU).
    Returns the parsed series and how many values needed the fallback."""
    text = series.astype("string").str.strip()
    parsed = pd.to_datetime(text, format="ISO8601", errors="coerce")
    retry_mask = parsed.isna() & text.notna() & (text != "")
    fallback_count = 0
    if retry_mask.any():
        retried = pd.to_datetime(text[retry_mask], dayfirst=True, errors="coerce", format="mixed")
        fallback_count = int(retried.notna().sum())
        parsed.loc[retry_mask] = retried
    return parsed.dt.normalize(), fallback_count


def validate_dataframe(raw: pd.DataFrame) -> ValidationResult:
    """Validate and clean a raw sales frame. Raises :class:`ValidationError`
    only for problems that make the whole file unusable."""
    issues: list[Issue] = []

    if raw is None or raw.empty:
        raise ValidationError("The file contains no data rows.")
    if len(raw) > MAX_UPLOAD_ROWS:
        raise ValidationError(
            f"The file has {len(raw):,} rows; the limit is {MAX_UPLOAD_ROWS:,}. "
            "Aggregate to weekly level or split the file."
        )

    df = raw.copy()
    rows_in = len(df)

    # 1. Headers and aliases -------------------------------------------------
    normalized = [normalize_header(c) for c in df.columns]
    renamed: list[str] = []
    final_names: list[str] = []
    for original, norm in zip(df.columns, normalized, strict=True):
        target = norm
        if norm not in ALL_COLUMNS and norm in COLUMN_ALIASES:
            target = COLUMN_ALIASES[norm]
        if target in final_names:  # keep the first column that maps to a name
            target = f"__dup__{norm}"
        if target != str(original) and not target.startswith("__dup__"):
            renamed.append(f"'{original}' -> '{target}'")
        final_names.append(target)
    df.columns = final_names
    if renamed:
        issues.append(Issue("Column names mapped", "info", 0, "Renamed to schema names",
                            "; ".join(renamed)))

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        hints = {}
        for alias, canonical in COLUMN_ALIASES.items():
            hints.setdefault(canonical, []).append(alias)
        hint_text = "; ".join(
            f"{m} (also accepted: {', '.join(sorted(hints.get(m, []))[:4]) or 'none'})" for m in missing
        )
        raise ValidationError(f"Missing required column(s): {hint_text}. "
                              "Download the import template for the exact format.")

    extra = [c for c in df.columns if c not in ALL_COLUMNS]
    if extra:
        shown = ", ".join(c.replace("__dup__", "") for c in extra[:8])
        issues.append(Issue("Unrecognised columns", "info", 0, "Ignored", shown))
        df = df.drop(columns=extra)

    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
            issues.append(Issue(f"Optional column '{col}' absent", "info", 0,
                                "Added as empty", "Related analyses will be limited."))

    # 2. Types ---------------------------------------------------------------
    for col in STRING_COLUMNS:
        s = df[col].astype("string").str.strip()
        df[col] = s.mask(s == "")

    for col in NUMERIC_COLUMNS:
        before_missing = df[col].isna() | (df[col].astype("string").str.strip() == "")
        parsed = parse_numeric(df[col])
        unparseable = int((parsed.isna() & ~before_missing).sum())
        if unparseable:
            issues.append(Issue(f"Non-numeric values in '{col}'", "warning", unparseable,
                                "Treated as missing"))
        df[col] = parsed

    df["promo_flag"] = _parse_bool(df["promo_flag"]) if df["promo_flag"].notna().any() else np.nan

    raw_dates = df["date"]
    df["date"], fallback = _parse_dates(raw_dates)
    if fallback:
        issues.append(Issue("Non-ISO dates", "info", fallback,
                            "Parsed assuming day-first (DD/MM/YYYY)"))
    bad_dates = int((df["date"].isna() & raw_dates.notna()).sum())
    if bad_dates:
        issues.append(Issue("Unparseable dates", "error", bad_dates, "Rows removed",
                            "Use YYYY-MM-DD."))

    # 3. Missing required values ----------------------------------------------
    missing_mask = pd.Series(False, index=df.index)
    for col in REQUIRED_COLUMNS:
        m = df[col].isna() & ~missing_mask  # count each removed row once
        n = int(m.sum()) - (bad_dates if col == "date" else 0)
        if n > 0:
            issues.append(Issue(f"Missing '{col}'", "error", n, "Rows removed"))
        missing_mask |= m
    df = df[~missing_mask]

    name_missing = df["product_name"].isna()
    if name_missing.any():
        issues.append(Issue("Missing product_name", "warning", int(name_missing.sum()),
                            "Filled with product_id"))
        df.loc[name_missing, "product_name"] = df.loc[name_missing, "product_id"]

    # 4. Impossible values ------------------------------------------------------
    rules = {
        "Non-positive selling_price": df["selling_price"] <= 0,
        "Non-positive original_price": df["original_price"] <= 0,
        "Negative unit_cost": df["unit_cost"] < 0,
        "Negative units_sold": df["units_sold"] < 0,
    }
    invalid_mask = pd.Series(False, index=df.index)
    for label, mask in rules.items():
        n = int((mask & ~invalid_mask).sum())
        if n:
            issues.append(Issue(label, "error", n, "Rows removed", "Price/quantity cannot be valid."))
        invalid_mask |= mask
    df = df[~invalid_mask].copy()

    fractional = (df["units_sold"] % 1 != 0)
    if fractional.any():
        issues.append(Issue("Fractional units_sold", "warning", int(fractional.sum()),
                            "Rounded to nearest unit"))
    df["units_sold"] = df["units_sold"].round().astype("int64")

    # 5. Repair-and-flag ----------------------------------------------------------
    bad_comp = df["competitor_price"] <= 0
    if bad_comp.any():
        issues.append(Issue("Zero/negative competitor_price", "warning", int(bad_comp.sum()),
                            "Set to missing", "Treated as 'not tracked'."))
        df.loc[bad_comp, "competitor_price"] = np.nan

    bad_stock = df["stock_on_hand"] < 0
    if bad_stock.any():
        issues.append(Issue("Negative stock_on_hand", "warning", int(bad_stock.sum()), "Set to missing"))
        df.loc[bad_stock, "stock_on_hand"] = np.nan

    above_list = df["selling_price"] > df["original_price"] * 1.001
    if above_list.any():
        issues.append(Issue("Selling price above list price", "warning", int(above_list.sum()),
                            "Kept; discount shows as negative", "Check list price or currency."))

    below_cost = df["selling_price"] < df["unit_cost"]
    if below_cost.any():
        issues.append(Issue("Sold below unit cost", "warning", int(below_cost.sum()),
                            "Kept; negative gross profit", "May be clearance or a cost error."))

    # Product attributes must be consistent per product_id (one category, one
    # brand, one name) or category/brand filters would disagree between SQL
    # and pandas. Standardise to the most frequent value and report it.
    for col in ("category", "brand", "product_name"):
        n_values = df.groupby("product_id")[col].nunique()
        conflicted = n_values[n_values > 1].index
        if len(conflicted):
            mode = df[df["product_id"].isin(conflicted)].groupby("product_id")[col] \
                .agg(lambda s: s.value_counts().index[0])
            affected = df["product_id"].isin(conflicted)
            df.loc[affected, col] = df.loc[affected, "product_id"].map(mode)
            issues.append(Issue(f"Inconsistent {col} per product_id", "warning", int(affected.sum()),
                                "Standardised to most frequent value",
                                f"{len(conflicted)} product(s) affected."))

    # 6. Duplicates ----------------------------------------------------------------
    exact_dupes = df.duplicated(keep="first")
    if exact_dupes.any():
        issues.append(Issue("Exact duplicate rows", "error", int(exact_dupes.sum()),
                            "Removed (kept first)"))
        df = df[~exact_dupes]
    key_dupes = df.duplicated(subset=list(KEY_COLUMNS), keep="first")
    if key_dupes.any():
        issues.append(Issue("Conflicting rows for same date/product/platform", "error",
                            int(key_dupes.sum()), "Removed (kept first)",
                            "Aggregate your export to one row per key."))
        df = df[~key_dupes]

    if df.empty:
        raise ValidationError("No valid rows remain after cleaning. See the issues listed above.")

    df = df[list(ALL_COLUMNS)].sort_values(list(KEY_COLUMNS)).reset_index(drop=True)
    for col in ("competitor_price", "stock_on_hand", "promo_flag"):
        df[col] = df[col].astype("float64")

    summary = build_summary(df, rows_in)
    return ValidationResult(data=df, issues=issues, summary=summary)


def build_summary(df: pd.DataFrame, rows_in: int | None = None) -> dict:
    """Data-quality summary for a clean frame."""
    rows_in = len(df) if rows_in is None else rows_in
    periods = df["date"].nunique()
    completeness = {c: float(df[c].notna().mean()) if len(df) else 0.0 for c in ALL_COLUMNS}
    return {
        "rows_in": int(rows_in),
        "rows_out": int(len(df)),
        "retained_pct": float(len(df) / rows_in) if rows_in else 0.0,
        "date_min": df["date"].min(),
        "date_max": df["date"].max(),
        "periods": int(periods),
        "products": int(df["product_id"].nunique()),
        "categories": int(df["category"].nunique()),
        "brands": int(df["brand"].nunique()),
        "platforms": int(df["platform"].nunique()),
        "competitor_coverage": completeness["competitor_price"],
        "completeness": completeness,
        "single_snapshot": bool(periods < 2),
    }
