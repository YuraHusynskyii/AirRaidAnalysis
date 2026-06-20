"""Data contracts and validation helpers for alert datasets."""

from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd


def validate_required_columns(
    df: pd.DataFrame, required_columns: Iterable[str]
) -> None:
    """Ensure that all required columns exist in the dataframe.

    Args:
        df: Input dataframe to validate.
        required_columns: Column names that must be present.

    Raises:
        ValueError: If dataframe is empty or required columns are missing.
    """
    if df.empty:
        raise ValueError("Input dataframe is empty.")

    missing = sorted(set(required_columns) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def validate_no_missing_values(df: pd.DataFrame, columns: Iterable[str]) -> None:
    """Ensure selected columns do not contain null values.

    Args:
        df: Input dataframe to validate.
        columns: Columns checked for nulls.

    Raises:
        ValueError: If any checked column contains null values.
    """
    checked = list(columns)
    null_counts = df[checked].isna().sum()
    invalid = null_counts[null_counts > 0]
    if not invalid.empty:
        details = ", ".join(f"{col}={count}" for col, count in invalid.items())
        raise ValueError(f"Null values detected in required columns: {details}")


def validate_no_duplicates(
    df: pd.DataFrame, subset: Optional[list[str]] = None
) -> None:
    """Ensure there are no duplicate rows for the selected key columns.

    Args:
        df: Input dataframe to validate.
        subset: Columns used as duplicate key. Defaults to all columns.

    Raises:
        ValueError: If duplicate rows are found.
    """
    duplicate_mask = df.duplicated(subset=subset, keep=False)
    duplicate_count = int(duplicate_mask.sum())
    if duplicate_count > 0:
        key = subset or list(df.columns)
        raise ValueError(
            f"Found {duplicate_count} duplicate rows for key columns: {key}"
        )


def validate_timezone(index: pd.DatetimeIndex, expected_timezone: str) -> None:
    """Ensure datetime index uses the expected IANA timezone.

    Args:
        index: Datetime index to validate.
        expected_timezone: Expected timezone name.

    Raises:
        ValueError: If index is not timezone-aware or timezone differs.
    """
    if index.tz is None:
        raise ValueError("Datetime index must be timezone-aware.")

    if str(index.tz) != expected_timezone:
        raise ValueError(
            f"Unexpected timezone: {index.tz}. Expected: {expected_timezone}."
        )
