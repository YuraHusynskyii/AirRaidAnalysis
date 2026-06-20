"""Data ingestion utilities for time-series datasets."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from src.schemas import (
    validate_no_duplicates,
    validate_no_missing_values,
    validate_required_columns,
)


def validate_raw_alerts(
    df: pd.DataFrame,
    datetime_column: str,
    region_column: Optional[str] = None,
) -> pd.DataFrame:
    """Validate raw alerts dataframe against project data contracts.

    Args:
        df: Raw alerts dataframe.
        datetime_column: Name of datetime column.
        region_column: Optional region column used for duplicate checks.

    Returns:
        pd.DataFrame: Validated dataframe copy.

    Raises:
        ValueError: If dataframe violates schema or quality constraints.
        RuntimeError: If validation fails unexpectedly.
    """
    required_columns = [datetime_column]
    if region_column:
        required_columns.append(region_column)

    try:
        validate_required_columns(df, required_columns)
        validate_no_missing_values(df, required_columns)
        duplicate_key = [datetime_column, region_column] if region_column else None
        validate_no_duplicates(df, subset=duplicate_key)
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Failed to validate raw alerts dataframe.") from exc

    return df.copy()


def load_alerts_csv(
    file_path: Path | str,
    datetime_column: str,
    region_column: Optional[str] = None,
    validate: bool = True,
) -> pd.DataFrame:
    """Load alerts dataset from CSV and parse datetime column.

    Args:
        file_path: Path to source CSV file.
        datetime_column: Name of datetime field to parse.
        region_column: Optional region column for duplicate validation.
        validate: Whether to run data contract checks after loading.

    Returns:
        pd.DataFrame: Loaded and optionally validated dataset.

    Raises:
        FileNotFoundError: If the source file does not exist.
        ValueError: If datetime column is absent or validation fails.
        RuntimeError: If file reading fails unexpectedly.
    """
    path_obj = Path(file_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Input file not found: {path_obj}")

    try:
        df = pd.read_csv(path_obj)
    except Exception as exc:
        raise RuntimeError(f"Failed to read CSV file: {path_obj}") from exc

    if datetime_column not in df.columns:
        raise ValueError(f"Missing datetime column: {datetime_column}")

    try:
        df[datetime_column] = pd.to_datetime(df[datetime_column], errors="raise")
    except Exception as exc:
        raise RuntimeError(
            f"Failed to parse datetime values in column: {datetime_column}"
        ) from exc

    if validate:
        df = validate_raw_alerts(
            df=df,
            datetime_column=datetime_column,
            region_column=region_column,
        )

    return df
