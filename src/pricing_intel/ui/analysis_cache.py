"""Cached heavy computations shared by several pages."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..db import Filters
from ..elasticity import binned_relationship, estimate_elasticities


@st.cache_data(show_spinner="Estimating elasticities…", max_entries=16)
def elasticities(dataset_key: str, filters: Filters, _df: pd.DataFrame) -> pd.DataFrame:
    return estimate_elasticities(_df)


@st.cache_data(show_spinner=False, max_entries=32)
def binned(dataset_key: str, filters: Filters, group: str, _df: pd.DataFrame) -> pd.DataFrame:
    return binned_relationship(_df)
