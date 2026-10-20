"""Shared fixtures."""

from __future__ import annotations

import pandas as pd
import pytest

from pricing_intel.data_generation import generate_dataset
from pricing_intel.validation import validate_dataframe


@pytest.fixture
def tiny_raw() -> pd.DataFrame:
    """Hand-computable dataset: 2 products x 2 platforms x 2 weeks."""
    return pd.DataFrame({
        "date": ["2025-01-06", "2025-01-06", "2025-01-13", "2025-01-13", "2025-01-06"],
        "product_id": ["A", "A", "A", "B", "B"],
        "product_name": ["Alpha", "Alpha", "Alpha", "Beta", "Beta"],
        "category": ["Cat1", "Cat1", "Cat1", "Cat2", "Cat2"],
        "brand": ["X", "X", "X", "Y", "Y"],
        "platform": ["P1", "P2", "P1", "P1", "P2"],
        "original_price": [100, 100, 100, 50, 50],
        "selling_price": [80, 90, 100, 50, 40],
        "competitor_price": [100, None, 95, 50, 0],
        "unit_cost": [50, 50, 50, 30, 30],
        "units_sold": [10, 5, 4, 20, 0],
        "stock_on_hand": [100, 100, 100, 100, 100],
        "promo_flag": [1, 0, 0, 0, 1],
    })


@pytest.fixture
def tiny_clean(tiny_raw) -> pd.DataFrame:
    return validate_dataframe(tiny_raw).data


@pytest.fixture(scope="session")
def small_panel() -> pd.DataFrame:
    """A reduced synthetic panel (fast) with known true elasticities."""
    return validate_dataframe(generate_dataset(seed=11, weeks=52, products_per_category=8)).data
