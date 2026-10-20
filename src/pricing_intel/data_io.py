"""Reading CSVs from disk or from a browser upload."""

from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from .config import MAX_UPLOAD_MB, SAMPLE_DATA_PATH
from .validation import ValidationError, ValidationResult, validate_dataframe

Source = str | Path | bytes | BinaryIO


def read_raw_csv(source: Source) -> pd.DataFrame:
    """Read a CSV as text columns (types are decided by validation).

    Accepts a path, raw bytes or a file-like object (e.g. Streamlit's
    ``UploadedFile``). Tries UTF-8 (with or without BOM) and falls back to
    Windows-1252, the usual encoding of Excel "CSV" exports on Windows.
    """
    if isinstance(source, (str, Path)):
        data = Path(source).read_bytes()
    elif isinstance(source, bytes):
        data = source
    else:
        data = source.read()

    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError(f"File is larger than {MAX_UPLOAD_MB} MB.")
    if not data.strip():
        raise ValidationError("The file is empty.")

    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return pd.read_csv(io.BytesIO(data), dtype=str, encoding=encoding,
                               keep_default_na=True, skipinitialspace=True)
        except UnicodeDecodeError as exc:
            last_error = exc
        except pd.errors.ParserError as exc:
            raise ValidationError(f"Could not parse the CSV: {exc}") from exc
        except pd.errors.EmptyDataError as exc:
            raise ValidationError("The file has no columns or rows.") from exc
    raise ValidationError(f"Unsupported text encoding ({last_error}). Save the file as UTF-8 CSV.")


def load_and_validate(source: Source) -> ValidationResult:
    """Read + validate in one step."""
    return validate_dataframe(read_raw_csv(source))


def load_sample() -> ValidationResult:
    """The bundled synthetic dataset, validated through the same pipeline as
    an upload (so the sample can never bypass the rules)."""
    if not SAMPLE_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Sample data not found at {SAMPLE_DATA_PATH}. Run: python scripts/generate_data.py"
        )
    return load_and_validate(SAMPLE_DATA_PATH)
