"""Tests for data contract validation."""

from __future__ import annotations

import pandas as pd
import pytest

from src.ingestion import validate_raw_alerts
from src.preprocessing import ensure_datetime_index
from src.schemas import (
    validate_no_duplicates,
    validate_no_missing_values,
    validate_required_columns,
    validate_timezone,
)


def test_validate_required_columns_success() -> None:
    """Valid dataframe passes required column checks."""
    df = pd.DataFrame({"timestamp": ["2024-01-01"], "region": ["Kyiv"]})
    validate_required_columns(df, ["timestamp", "region"])


def test_validate_required_columns_missing_raises() -> None:
    """Missing required columns raise ValueError."""
    df = pd.DataFrame({"timestamp": ["2024-01-01"]})
    with pytest.raises(ValueError, match="Missing required columns"):
        validate_required_columns(df, ["timestamp", "region"])


def test_validate_no_missing_values_raises() -> None:
    """Null values in required columns raise ValueError."""
    df = pd.DataFrame({"timestamp": ["2024-01-01", None], "region": ["Kyiv", "Lviv"]})
    with pytest.raises(ValueError, match="Null values detected"):
        validate_no_missing_values(df, ["timestamp", "region"])


def test_validate_no_duplicates_raises() -> None:
    """Duplicate key rows raise ValueError."""
    df = pd.DataFrame(
        {
            "timestamp": ["2024-01-01", "2024-01-01"],
            "region": ["Kyiv", "Kyiv"],
        }
    )
    with pytest.raises(ValueError, match="duplicate rows"):
        validate_no_duplicates(df, subset=["timestamp", "region"])


def test_validate_raw_alerts_success() -> None:
    """Raw alerts validation accepts clean input."""
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2024-01-01 10:00", "2024-01-01 11:00"]),
            "region": ["Kyiv", "Lviv"],
        }
    )
    validated = validate_raw_alerts(
        df=df,
        datetime_column="timestamp",
        region_column="region",
    )
    assert len(validated) == 2


def test_ensure_datetime_index_sets_timezone() -> None:
    """Datetime index is localized and passes timezone contract."""
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2024-01-01 10:00", "2024-01-01 11:00"]),
            "region": ["Kyiv", "Lviv"],
        }
    )
    indexed = ensure_datetime_index(
        df=df,
        datetime_column="timestamp",
        timezone="Europe/Kyiv",
    )
    validate_timezone(indexed.index, expected_timezone="Europe/Kyiv")
