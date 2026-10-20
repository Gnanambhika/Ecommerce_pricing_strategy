"""Reproducible synthetic e-commerce pricing dataset.

The generator simulates weekly sales for fictional products sold on three
fictional channels. It is designed to be *useful for teaching pricing
analytics*, not to mimic any real retailer:

* Demand follows a constant-elasticity model with a **known true elasticity per
  category** (``TRUE_ELASTICITY``), so the estimator in ``elasticity.py`` can
  be checked against ground truth.
* Promotions are deliberately **more frequent during the festive season**, when
  baseline demand is also higher. That is a realistic confounder: a naive
  price-vs-units regression mistakes seasonal lift for price response.
* Competitor prices move partly independently, are missing for some series
  (not tracked) and some weeks (scrape gaps), as in real competitive data.
* Occasional low-stock weeks cap sales (demand censoring).

Everything is driven by one ``numpy.random.Generator`` seeded with ``seed``,
so the same seed always reproduces the same CSV.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

DEFAULT_SEED = 42
DEFAULT_START = "2025-01-06"  # a Monday
DEFAULT_WEEKS = 78


@dataclass(frozen=True)
class CategorySpec:
    name: str
    product_types: tuple[str, ...]
    list_price_range: tuple[float, float]
    cost_ratio_range: tuple[float, float]  # unit cost / list price
    true_elasticity: float
    base_units_range: tuple[float, float]  # weekly units on the main channel
    promo_depths: tuple[float, ...]
    festive_sensitivity: float


CATEGORIES: tuple[CategorySpec, ...] = (
    CategorySpec("Electronics", ("Wireless Earbuds", "Smartwatch", "Bluetooth Speaker",
                                 "Power Bank", "Fitness Band", "USB-C Hub"),
                 (999, 14999), (0.55, 0.72), -1.8, (25, 140), (0.10, 0.15, 0.20, 0.25), 0.55),
    CategorySpec("Home & Kitchen", ("Air Fryer", "Mixer Grinder", "Cookware Set",
                                    "Water Bottle", "Storage Jars", "Electric Kettle"),
                 (349, 7999), (0.42, 0.60), -1.5, (30, 180), (0.10, 0.15, 0.20, 0.30), 0.45),
    CategorySpec("Beauty & Personal Care", ("Face Serum", "Sunscreen", "Hair Dryer",
                                            "Beard Trimmer", "Body Lotion", "Lip Care Kit"),
                 (199, 3999), (0.30, 0.48), -1.3, (40, 240), (0.10, 0.15, 0.20, 0.25), 0.35),
    CategorySpec("Fashion", ("Running Shoes", "Denim Jacket", "Cotton T-Shirt",
                                 "Backpack", "Sunglasses", "Analog Watch"),
                 (499, 5999), (0.32, 0.50), -2.2, (20, 160), (0.15, 0.25, 0.35, 0.40), 0.70),
    CategorySpec("Sports & Outdoors", ("Yoga Mat", "Dumbbell Set", "Cycling Helmet",
                                       "Badminton Racket", "Trekking Pole", "Skipping Rope"),
                 (249, 6999), (0.45, 0.62), -1.6, (15, 120), (0.10, 0.15, 0.20, 0.25), 0.30),
    CategorySpec("Books & Stationery", ("Notebook Pack", "Fountain Pen", "Planner",
                                        "Desk Organizer", "Art Marker Set", "Paperback Novel"),
                 (149, 1499), (0.40, 0.58), -0.9, (35, 220), (0.05, 0.10, 0.15, 0.20), 0.20),
)

TRUE_ELASTICITY: dict[str, float] = {c.name: c.true_elasticity for c in CATEGORIES}

BRANDS_BY_CATEGORY: dict[str, tuple[str, ...]] = {
    "Electronics": ("Velora", "Kestrel", "Zenvolt"),
    "Home & Kitchen": ("Oakmont", "Hearthly", "Kestrel"),
    "Beauty & Personal Care": ("Lumina", "Petalyn", "Mistral Glow"),
    "Fashion": ("Northwind", "Urban Loom", "Saffra"),
    "Sports & Outdoors": ("Peakline", "Strideon", "Northwind"),
    "Books & Stationery": ("Inkwell", "Papyra", "Quillon"),
}


@dataclass(frozen=True)
class PlatformSpec:
    name: str
    demand_multiplier: float
    price_multiplier: float
    coverage: float  # probability a product is listed here
    promo_multiplier: float


PLATFORMS: tuple[PlatformSpec, ...] = (
    PlatformSpec("Marketplace North", 1.00, 1.00, 1.00, 1.0),
    PlatformSpec("Marketplace South", 0.70, 1.02, 0.85, 1.0),
    PlatformSpec("Direct Store (D2C)", 0.35, 1.04, 0.60, 0.5),
)

PRODUCTS_PER_CATEGORY = 20
CROSS_PRICE_ELASTICITY = 0.4  # demand response to competitor/own price ratio


def _festive_weight(dates: pd.DatetimeIndex) -> np.ndarray:
    """0..1 weight for the festive season (October to mid-November) and a
    smaller year-end sale. Applied identically every year."""
    doy = dates.dayofyear.to_numpy()
    festive = ((doy >= 274) & (doy <= 320)).astype(float)  # ~1 Oct - 16 Nov
    year_end = ((doy >= 352) | (doy <= 5)).astype(float) * 0.5
    return np.maximum(festive, year_end)


def generate_dataset(
    seed: int = DEFAULT_SEED,
    start: str = DEFAULT_START,
    weeks: int = DEFAULT_WEEKS,
    products_per_category: int = PRODUCTS_PER_CATEGORY,
) -> pd.DataFrame:
    """Generate the synthetic weekly sales panel as a tidy DataFrame."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start=start, periods=weeks, freq="7D")
    t = np.arange(weeks)
    week_of_year = dates.isocalendar().week.to_numpy().astype(float)
    festive = _festive_weight(dates)
    annual = 1 + 0.10 * np.sin(2 * np.pi * (week_of_year - 12) / 52)
    trend = 1 + 0.12 * t / 52

    frames: list[pd.DataFrame] = []
    sku_counter = 0
    for cat in CATEGORIES:
        brands = BRANDS_BY_CATEGORY[cat.name]
        for i in range(products_per_category):
            sku_counter += 1
            product_id = f"SKU-{sku_counter:04d}"
            brand = brands[i % len(brands)]
            ptype = cat.product_types[i % len(cat.product_types)]
            product_name = f"{brand} {ptype} {i // len(cat.product_types) + 1}"

            lo, hi = cat.list_price_range
            list_price = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
            list_price = max(round(list_price / 10) * 10 - 1, 99.0)
            cost_ratio = rng.uniform(*cat.cost_ratio_range)
            everyday_disc = rng.uniform(0.0, 0.10)
            base_units = rng.uniform(*cat.base_units_range)
            comp_factor = rng.normal(1.0, 0.06)
            comp_everyday = rng.uniform(0.0, 0.12)

            # Cost drifts up ~3 % a year (input inflation).
            unit_cost_path = list_price * cost_ratio * (1 + 0.03 * t / 52) * rng.normal(1, 0.01, weeks)

            for plat in PLATFORMS:
                if rng.random() > plat.coverage:
                    continue
                plat_list = round(list_price * plat.price_multiplier / 10) * 10 - 1

                promo_prob = (0.10 + 0.35 * festive) * plat.promo_multiplier
                promo = rng.random(weeks) < promo_prob
                depth = rng.choice(cat.promo_depths, size=weeks)
                noise_disc = rng.uniform(0.0, 0.03, weeks)
                disc = np.where(promo, depth, everyday_disc + noise_disc)
                selling = np.round(plat_list * (1 - disc), 0)

                # Competitor: own promotions, partly overlapping the festive season.
                comp_promo = rng.random(weeks) < (0.12 + 0.20 * festive)
                comp_depth = rng.uniform(0.08, 0.25, weeks)
                comp_true = list_price * comp_factor * (1 - comp_everyday) \
                    * np.where(comp_promo, 1 - comp_depth, 1.0) * rng.normal(1, 0.015, weeks)
                comp_true = np.round(comp_true, 0)

                ref_price = plat_list * (1 - everyday_disc)
                season = annual * (1 + cat.festive_sensitivity * festive)
                # Cross-price effect uses the competitor's price relative to its OWN usual
                # level, so it does not alter our own-price elasticity.
                comp_usual = list_price * comp_factor * (1 - comp_everyday)
                expected = (
                    base_units * plat.demand_multiplier * trend * season
                    * (selling / ref_price) ** cat.true_elasticity
                    * (comp_true / comp_usual) ** CROSS_PRICE_ELASTICITY
                    * rng.lognormal(0.0, 0.12, weeks)
                )
                units = rng.poisson(np.maximum(expected, 0.05))

                stock = np.round(expected * rng.uniform(1.6, 4.0, weeks)).astype(int) + 5
                stockout = rng.random(weeks) < 0.02
                stock = np.where(stockout, np.round(expected * rng.uniform(0.3, 0.8, weeks)), stock).astype(int)
                units = np.minimum(units, stock)

                # Competitor tracking gaps: whole series untracked or random weeks missing.
                observed_comp = comp_true.astype(float)
                if rng.random() < 0.08:
                    observed_comp[:] = np.nan
                else:
                    observed_comp[rng.random(weeks) < 0.05] = np.nan

                frames.append(pd.DataFrame({
                    "date": dates.strftime("%Y-%m-%d"),
                    "product_id": product_id,
                    "product_name": product_name,
                    "category": cat.name,
                    "brand": brand,
                    "platform": plat.name,
                    "original_price": float(plat_list),
                    "selling_price": selling,
                    "competitor_price": observed_comp,
                    "unit_cost": np.round(unit_cost_path, 2),
                    "units_sold": units.astype(int),
                    "stock_on_hand": stock,
                    "promo_flag": promo.astype(int),
                }))

    df = pd.concat(frames, ignore_index=True)
    return df.sort_values(["date", "product_id", "platform"]).reset_index(drop=True)


def make_messy_example(clean: pd.DataFrame, seed: int = 7, n_rows: int = 400) -> pd.DataFrame:
    """Build a small *deliberately broken* CSV that exercises every validation
    rule: aliased headers, currency-formatted numbers, duplicates, missing
    values, invalid prices and unparseable dates. Used by the import demo."""
    rng = np.random.default_rng(seed)
    sample = clean.sample(n=n_rows, random_state=seed).reset_index(drop=True)
    messy = sample.astype(object).copy()

    def pick(k: int) -> np.ndarray:
        return rng.choice(len(messy), size=k, replace=False)

    for idx in pick(6):
        messy.at[idx, "selling_price"] = f"₹{float(sample.at[idx, 'selling_price']):,.0f}"
    for idx in pick(4):
        messy.at[idx, "selling_price"] = -abs(float(sample.at[idx, "selling_price"]))
    for idx in pick(3):
        messy.at[idx, "selling_price"] = 0
    for idx in pick(6):
        messy.at[idx, "units_sold"] = None
    for idx in pick(3):
        messy.at[idx, "date"] = rng.choice(["31/02/2025", "not a date", ""])
    for idx in pick(4):
        messy.at[idx, "selling_price"] = float(sample.at[idx, "original_price"]) * 1.15
    for idx in pick(3):
        messy.at[idx, "competitor_price"] = 0
    for idx in pick(3):
        messy.at[idx, "unit_cost"] = float(sample.at[idx, "selling_price"]) * 1.2

    # Exact duplicates and conflicting duplicates on the business key.
    exact = messy.iloc[pick(10)]
    conflicting = messy.iloc[pick(5)].copy()
    conflicting["units_sold"] = [int(rng.integers(1, 50)) for _ in range(len(conflicting))]
    messy = pd.concat([messy, exact, conflicting], ignore_index=True)

    return messy.rename(columns={
        "product_id": "SKU",
        "original_price": "MRP",
        "selling_price": "Sale Price",
        "units_sold": "Qty",
        "platform": "Channel",
    })
