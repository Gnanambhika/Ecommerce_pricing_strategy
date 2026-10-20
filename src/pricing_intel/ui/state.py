"""Session state: active dataset, cached database and global filters."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from ..data_io import load_sample
from ..db import Filters, PricingDatabase
from ..metrics import add_row_metrics
from ..validation import ValidationResult
from . import components as ui

UPLOAD_KEY = "uploaded_dataset"
SAMPLE_KEY = "sample"


@dataclass
class ActiveDataset:
    key: str
    label: str
    synthetic: bool
    result: ValidationResult

    @property
    def data(self) -> pd.DataFrame:
        return self.result.data


@st.cache_data(show_spinner="Loading sample dataset…")
def _cached_sample() -> ValidationResult:
    return load_sample()


@st.cache_resource(max_entries=4, show_spinner="Building analytics database…")
def _cached_db(dataset_key: str, _df: pd.DataFrame) -> PricingDatabase:
    return PricingDatabase(_df)


def dataset_key_for_bytes(data: bytes) -> str:
    return "upload-" + hashlib.sha256(data).hexdigest()[:16]


def active_dataset() -> ActiveDataset:
    upload = st.session_state.get(UPLOAD_KEY)
    if upload is not None:
        return upload
    return ActiveDataset(SAMPLE_KEY, "Sample dataset (synthetic)", True, _cached_sample())


def set_uploaded(key: str, filename: str, result: ValidationResult) -> None:
    st.session_state[UPLOAD_KEY] = ActiveDataset(key, f"Uploaded: {filename}", False, result)
    reset_filters()


def clear_uploaded() -> None:
    st.session_state.pop(UPLOAD_KEY, None)
    reset_filters()


def database(ds: ActiveDataset) -> PricingDatabase:
    return _cached_db(ds.key, ds.data)


# --- Filters -------------------------------------------------------------------
_FILTER_WIDGETS = ("f_dates", "f_categories", "f_brands", "f_platforms")


def reset_filters() -> None:
    for k in _FILTER_WIDGETS:
        st.session_state.pop(k, None)


def render_sidebar_filters(ds: ActiveDataset) -> Filters:
    df = ds.data
    min_d = df["date"].min().date()
    max_d = df["date"].max().date()

    st.sidebar.markdown('<div class="sidebar-section">Filters</div>', unsafe_allow_html=True)
    picked = st.sidebar.date_input(
        "Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d, key="f_dates",
        help="Period start dates to include. Applies to every analysis page.", format="YYYY-MM-DD",
    )
    if isinstance(picked, (tuple, list)):
        start = picked[0] if len(picked) > 0 else min_d
        end = picked[1] if len(picked) > 1 else max_d
    else:
        start, end = picked, picked

    categories = st.sidebar.multiselect(
        "Category", sorted(df["category"].unique()), key="f_categories", placeholder="All categories",
    )
    brand_pool = df if not categories else df[df["category"].isin(categories)]
    brand_options = sorted(brand_pool["brand"].unique())
    # Drop stale brand selections when the category filter narrows the options.
    if "f_brands" in st.session_state:
        st.session_state["f_brands"] = [b for b in st.session_state["f_brands"] if b in brand_options]
    brands = st.sidebar.multiselect("Brand", brand_options, key="f_brands", placeholder="All brands")
    platforms = st.sidebar.multiselect(
        "Platform", sorted(df["platform"].unique()), key="f_platforms", placeholder="All platforms",
    )
    if st.sidebar.button("Reset filters", type="secondary"):
        reset_filters()
        st.rerun()

    return Filters(start_date=start, end_date=end, categories=tuple(categories),
                   brands=tuple(brands), platforms=tuple(platforms))


def apply_filters(df: pd.DataFrame, f: Filters) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    if f.start_date is not None:
        mask &= df["date"] >= pd.Timestamp(f.start_date)
    if f.end_date is not None:
        mask &= df["date"] <= pd.Timestamp(f.end_date)
    if f.categories:
        mask &= df["category"].isin(f.categories)
    if f.brands:
        mask &= df["brand"].isin(f.brands)
    if f.platforms:
        mask &= df["platform"].isin(f.platforms)
    return df[mask]


@st.cache_data(show_spinner=False, max_entries=32)
def filtered_frame(dataset_key: str, f: Filters, _df: pd.DataFrame) -> pd.DataFrame:
    return add_row_metrics(apply_filters(_df, f))


def previous_period(f: Filters, min_date: date) -> Filters | None:
    """Same-length window immediately before the selection (for KPI deltas)."""
    if f.start_date is None or f.end_date is None:
        return None
    length = (f.end_date - f.start_date).days
    prev_end = f.start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length)
    if prev_end < min_date:
        return None
    return Filters(prev_start, prev_end, f.categories, f.brands, f.platforms)


@dataclass
class PageContext:
    dataset: ActiveDataset
    db: PricingDatabase
    filters: Filters
    df: pd.DataFrame  # filtered, with row metrics

    @property
    def badges(self) -> list[tuple[str, str]]:
        out = []
        if self.dataset.synthetic:
            out.append(("Synthetic data, not real marketplace evidence", "synthetic"))
        else:
            out.append((self.dataset.label, ""))
        f = self.filters
        if f.start_date and f.end_date:
            out.append((f"{f.start_date:%d %b %Y} – {f.end_date:%d %b %Y}", ""))
        n_filters = sum(bool(x) for x in (f.categories, f.brands, f.platforms))
        if n_filters:
            out.append((f"{n_filters} filter{'s' if n_filters > 1 else ''} applied", ""))
        return out


def page_context() -> PageContext:
    """Called at the top of every page."""
    ds = active_dataset()
    f = st.session_state.get("filters") or Filters()
    return PageContext(ds, database(ds), f, filtered_frame(ds.key, f, ds.data))


def require_rows(ctx: PageContext) -> bool:
    if ctx.df.empty:
        ui.empty_state()
        return False
    return True
