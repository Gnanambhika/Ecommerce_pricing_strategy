"""Dataset contract: the single source of truth for column names, types and
meaning. Used by validation, the import template, the in-app data dictionary
and the README.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    name: str
    dtype: str  # "date" | "string" | "float" | "int" | "bool"
    required: bool
    description: str
    example: str


COLUMNS: tuple[Column, ...] = (
    Column("date", "date", True,
           "Start of the trading period (weekly in the sample data). ISO format YYYY-MM-DD.",
           "2025-03-03"),
    Column("product_id", "string", True,
           "Stable product identifier (SKU).", "SKU-0001"),
    Column("product_name", "string", False,
           "Human-readable product name. Defaults to product_id when missing.",
           "Velora Wireless Earbuds 1"),
    Column("category", "string", True,
           "Merchandising category.", "Electronics"),
    Column("brand", "string", True, "Brand name.", "Velora"),
    Column("platform", "string", True,
           "Sales channel or marketplace where the units were sold.", "Marketplace North"),
    Column("original_price", "float", True,
           "List price / MRP before any discount, per unit.", "2499"),
    Column("selling_price", "float", True,
           "Actual average transaction price per unit after discounts.", "1999"),
    Column("competitor_price", "float", False,
           "Observed comparable competitor price per unit. Blank when not tracked.", "2099"),
    Column("unit_cost", "float", True,
           "Landed cost of goods per unit (purchase + inbound freight).", "1180"),
    Column("units_sold", "int", True,
           "Units sold in the period (net of cancellations, before returns).", "142"),
    Column("stock_on_hand", "int", False,
           "Units in stock at the start of the period.", "560"),
    Column("promo_flag", "bool", False,
           "1 if a planned promotion ran in the period, else 0.", "1"),
)

REQUIRED_COLUMNS: tuple[str, ...] = tuple(c.name for c in COLUMNS if c.required)
OPTIONAL_COLUMNS: tuple[str, ...] = tuple(c.name for c in COLUMNS if not c.required)
ALL_COLUMNS: tuple[str, ...] = tuple(c.name for c in COLUMNS)
NUMERIC_COLUMNS: tuple[str, ...] = tuple(
    c.name for c in COLUMNS if c.dtype in ("float", "int")
)
KEY_COLUMNS: tuple[str, ...] = ("date", "product_id", "platform")

# Common alternative headers seen in marketplace exports, mapped to the
# canonical schema. Matching happens after lower-casing and replacing spaces /
# hyphens with underscores.
COLUMN_ALIASES: dict[str, str] = {
    "week": "date",
    "period": "date",
    "order_date": "date",
    "sku": "product_id",
    "product": "product_name",
    "name": "product_name",
    "title": "product_name",
    "channel": "platform",
    "marketplace": "platform",
    "mrp": "original_price",
    "list_price": "original_price",
    "regular_price": "original_price",
    "price": "selling_price",
    "sale_price": "selling_price",
    "net_price": "selling_price",
    "competitor": "competitor_price",
    "comp_price": "competitor_price",
    "cost": "unit_cost",
    "cogs_per_unit": "unit_cost",
    "units": "units_sold",
    "quantity": "units_sold",
    "qty": "units_sold",
    "stock": "stock_on_hand",
    "inventory": "stock_on_hand",
    "promo": "promo_flag",
    "on_promotion": "promo_flag",
}


def data_dictionary() -> list[dict[str, str]]:
    """Rows for the in-app / README data dictionary."""
    return [
        {
            "Column": c.name,
            "Type": c.dtype,
            "Required": "Yes" if c.required else "No",
            "Description": c.description,
            "Example": c.example,
        }
        for c in COLUMNS
    ]
