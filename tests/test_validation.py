"""Import validation: schema, aliases, parsing, missing values, invalid prices,
duplicates and the data-quality summary."""

from __future__ import annotations

import pandas as pd
import pytest

from pricing_intel.data_io import read_raw_csv
from pricing_intel.validation import ValidationError, normalize_header, parse_numeric, validate_dataframe


def issue(result, check_fragment):
    found = [i for i in result.issues if check_fragment.lower() in i.check.lower()]
    return found[0] if found else None


def test_clean_data_passes_without_errors(tiny_raw):
    res = validate_dataframe(tiny_raw)
    assert not [i for i in res.issues if i.severity == "error"]
    assert res.summary["rows_out"] == len(tiny_raw)


def test_missing_required_column_is_fatal_with_helpful_message(tiny_raw):
    with pytest.raises(ValidationError, match="unit_cost"):
        validate_dataframe(tiny_raw.drop(columns=["unit_cost"]))


def test_empty_frame_is_fatal():
    with pytest.raises(ValidationError):
        validate_dataframe(pd.DataFrame())


def test_aliases_are_mapped(tiny_raw):
    raw = tiny_raw.rename(columns={"product_id": "SKU", "original_price": "MRP", "units_sold": "Qty",
                                   "platform": "Channel", "selling_price": "Sale Price"})
    res = validate_dataframe(raw)
    assert issue(res, "column names mapped") is not None
    assert {"product_id", "original_price", "units_sold", "platform", "selling_price"} <= set(res.data.columns)


@pytest.mark.parametrize("header, expected", [
    ("  Sale Price ", "sale_price"), ("﻿Date", "date"), ("Unit-Cost", "unit_cost"), ("A.B/C", "a_b_c"),
])
def test_normalize_header(header, expected):
    assert normalize_header(header) == expected


def test_currency_strings_are_parsed():
    out = parse_numeric(pd.Series(["₹1,299", "Rs. 450", "$12.5", "", None, "abc"]))
    assert out.iloc[0] == 1299 and out.iloc[1] == 450 and out.iloc[2] == 12.5
    assert out.iloc[3:].isna().all()


def test_non_positive_selling_price_rows_removed(tiny_raw):
    raw = tiny_raw.copy()
    raw.loc[0, "selling_price"] = -5
    raw.loc[1, "selling_price"] = 0
    res = validate_dataframe(raw)
    assert res.summary["rows_out"] == len(raw) - 2
    assert issue(res, "Non-positive selling_price").rows == 2


def test_negative_units_and_cost_removed(tiny_raw):
    raw = tiny_raw.copy()
    raw.loc[0, "units_sold"] = -1
    raw.loc[1, "unit_cost"] = -10
    res = validate_dataframe(raw)
    assert res.summary["rows_out"] == len(raw) - 2


def test_missing_required_values_removed(tiny_raw):
    raw = tiny_raw.copy()
    raw.loc[0, "units_sold"] = None
    raw.loc[1, "category"] = "   "
    res = validate_dataframe(raw)
    assert res.summary["rows_out"] == len(raw) - 2
    assert issue(res, "Missing 'units_sold'").rows == 1
    assert issue(res, "Missing 'category'").rows == 1


def test_bad_dates_removed_and_day_first_parsed(tiny_raw):
    raw = tiny_raw.copy()
    raw["date"] = raw["date"].astype(object)
    raw.loc[0, "date"] = "not a date"
    raw.loc[1, "date"] = "13/01/2025"
    res = validate_dataframe(raw)
    assert issue(res, "Unparseable dates").rows == 1
    assert issue(res, "Non-ISO dates").rows == 1
    assert pd.Timestamp("2025-01-13") in set(res.data["date"])


def test_zero_competitor_price_becomes_missing(tiny_raw):
    res = validate_dataframe(tiny_raw)
    assert issue(res, "competitor_price").rows == 1
    assert res.data["competitor_price"].isna().sum() == 2  # one blank + one zero


def test_soft_warnings_keep_rows(tiny_raw):
    raw = tiny_raw.copy()
    raw.loc[0, "selling_price"] = 120  # above list price 100
    raw.loc[1, "selling_price"] = 40   # below cost 50
    res = validate_dataframe(raw)
    assert res.summary["rows_out"] == len(raw)
    assert issue(res, "above list price").severity == "warning"
    assert issue(res, "below unit cost").severity == "warning"


def test_exact_and_key_duplicates_removed(tiny_raw):
    conflicting = tiny_raw.iloc[[0]].copy()
    conflicting["units_sold"] = 99
    raw = pd.concat([tiny_raw, tiny_raw.iloc[[1, 2]], conflicting], ignore_index=True)
    res = validate_dataframe(raw)
    assert issue(res, "Exact duplicate").rows == 2
    assert issue(res, "Conflicting rows").rows == 1
    assert res.summary["rows_out"] == len(tiny_raw)
    kept = res.data[(res.data["product_id"] == "A") & (res.data["platform"] == "P1")
                    & (res.data["date"] == "2025-01-06")]
    assert kept["units_sold"].iloc[0] == 10  # first occurrence kept


def test_inconsistent_category_is_standardised(tiny_raw):
    raw = pd.concat([tiny_raw, tiny_raw.iloc[[0]].assign(date="2025-01-20")], ignore_index=True)
    raw.loc[len(raw) - 1, "category"] = "Typo"
    res = validate_dataframe(raw)
    assert res.data.loc[res.data["product_id"] == "A", "category"].nunique() == 1
    assert issue(res, "Inconsistent category") is not None


def test_optional_columns_may_be_absent(tiny_raw):
    res = validate_dataframe(tiny_raw.drop(columns=["competitor_price", "stock_on_hand", "promo_flag",
                                                    "product_name"]))
    assert res.data["competitor_price"].isna().all()
    assert (res.data["product_name"] == res.data["product_id"]).all()


def test_all_rows_invalid_is_fatal(tiny_raw):
    raw = tiny_raw.assign(selling_price=0)
    with pytest.raises(ValidationError, match="No valid rows"):
        validate_dataframe(raw)


def test_single_snapshot_flagged(tiny_raw):
    res = validate_dataframe(tiny_raw[tiny_raw["date"] == "2025-01-06"])
    assert res.summary["single_snapshot"] is True


def test_read_raw_csv_handles_bom_and_cp1252():
    utf8 = "﻿date,product_id\n2025-01-06,A\n".encode()
    assert list(read_raw_csv(utf8).columns) == ["date", "product_id"]
    cp1252 = "date,product_name\n2025-01-06,Caf\xe9\n".encode("cp1252")
    assert read_raw_csv(cp1252).iloc[0, 1] == "Café"


def test_read_raw_csv_empty():
    with pytest.raises(ValidationError):
        read_raw_csv(b"   ")


def test_messy_example_is_cleaned():
    from pricing_intel.config import MESSY_SAMPLE_PATH
    if not MESSY_SAMPLE_PATH.exists():
        pytest.skip("messy example not generated")
    res = validate_dataframe(read_raw_csv(MESSY_SAMPLE_PATH))
    checks = {i.check for i in res.issues}
    assert any("duplicate" in c.lower() for c in checks)
    assert any("selling_price" in c for c in checks)
    assert res.summary["rows_out"] < res.summary["rows_in"]
