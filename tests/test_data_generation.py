"""Synthetic generator: reproducible, schema-valid, clearly fictional."""

from __future__ import annotations

import pandas as pd

from pricing_intel.config import SAMPLE_DATA_PATH
from pricing_intel.data_generation import TRUE_ELASTICITY, generate_dataset
from pricing_intel.schema import ALL_COLUMNS
from pricing_intel.validation import validate_dataframe


def test_same_seed_same_data():
    a = generate_dataset(seed=3, weeks=10, products_per_category=2)
    b = generate_dataset(seed=3, weeks=10, products_per_category=2)
    pd.testing.assert_frame_equal(a, b)


def test_different_seed_different_data():
    a = generate_dataset(seed=3, weeks=10, products_per_category=2)
    b = generate_dataset(seed=4, weeks=10, products_per_category=2)
    assert not a["units_sold"].equals(b["units_sold"])


def test_generated_data_is_schema_valid(small_panel):
    assert list(small_panel.columns) == list(ALL_COLUMNS)
    res = validate_dataframe(generate_dataset(seed=5, weeks=12, products_per_category=3))
    assert not [i for i in res.issues if i.severity == "error"]


def test_business_invariants(small_panel):
    d = small_panel
    assert (d["selling_price"] > 0).all()
    assert (d["selling_price"] <= d["original_price"] + 1e-9).all()
    assert (d["unit_cost"] > 0).all()
    assert (d["units_sold"] >= 0).all()
    assert (d["units_sold"] <= d["stock_on_hand"]).all()
    assert 0.05 < d["competitor_price"].isna().mean() < 0.25
    assert set(d["category"]) == set(TRUE_ELASTICITY)


def test_bundled_sample_matches_generator():
    """The committed CSV must be exactly what the seeded generator produces."""
    if not SAMPLE_DATA_PATH.exists():
        return
    committed = pd.read_csv(SAMPLE_DATA_PATH)
    fresh = generate_dataset()
    assert len(committed) == len(fresh)
    assert committed["units_sold"].sum() == fresh["units_sold"].sum()
    assert abs(committed["selling_price"].sum() - fresh["selling_price"].sum()) < 1
