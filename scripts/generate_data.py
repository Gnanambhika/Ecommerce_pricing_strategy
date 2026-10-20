"""Regenerate the bundled synthetic dataset, the messy import example and the
import template.

    python scripts/generate_data.py            # default seed 42
    python scripts/generate_data.py --seed 7   # a different, still reproducible draw
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pricing_intel.config import MESSY_SAMPLE_PATH, SAMPLE_DATA_PATH, TEMPLATE_PATH  # noqa: E402
from pricing_intel.data_generation import DEFAULT_SEED, generate_dataset, make_messy_example  # noqa: E402
from pricing_intel.schema import ALL_COLUMNS  # noqa: E402
from pricing_intel.validation import validate_dataframe  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    df = generate_dataset(seed=args.seed)
    result = validate_dataframe(df)
    blocking = [i for i in result.issues if i.severity == "error"]
    if blocking:
        raise SystemExit(f"Generated data failed validation: {blocking}")

    SAMPLE_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SAMPLE_DATA_PATH, index=False, float_format="%.2f", encoding="utf-8", lineterminator="\n")
    make_messy_example(df).to_csv(MESSY_SAMPLE_PATH, index=False, encoding="utf-8", lineterminator="\n")

    TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.head(3)[list(ALL_COLUMNS)].to_csv(TEMPLATE_PATH, index=False, float_format="%.2f",
                                         encoding="utf-8", lineterminator="\n")

    s = result.summary
    print(f"Wrote {len(df):,} rows -> {SAMPLE_DATA_PATH.relative_to(ROOT)}")
    print(f"  {s['products']} products, {s['platforms']} platforms, {s['periods']} weeks "
          f"({s['date_min']:%Y-%m-%d} to {s['date_max']:%Y-%m-%d}), "
          f"competitor coverage {s['competitor_coverage']:.1%}")
    print(f"Wrote messy example -> {MESSY_SAMPLE_PATH.relative_to(ROOT)}")
    print(f"Wrote import template -> {TEMPLATE_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
