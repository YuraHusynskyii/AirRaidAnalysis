"""Tests for feature engineering helpers."""

from __future__ import annotations

import pandas as pd
import pytest

from src.features import add_lag_features, add_time_features, build_features


def _hourly_frame(values: list[int]) -> pd.DataFrame:
    index = pd.date_range("2024-06-01", periods=len(values), freq="h")
    return pd.DataFrame({"alert_count": values}, index=index)


def test_add_time_features_creates_calendar_columns() -> None:
    """Calendar features are derived from datetime index."""
    df = _hourly_frame([1, 2, 3, 4])
    featured = add_time_features(df)

    assert {"hour", "day_of_week", "is_weekend"}.issubset(featured.columns)
    assert featured["hour"].between(0, 23).all()


def test_add_lag_features_creates_expected_columns() -> None:
    """Lag columns follow the configured lag list."""
    df = _hourly_frame([1, 2, 3, 4, 5])
    featured = add_lag_features(df, target_column="alert_count", lags=[1, 2])

    assert "alert_count_lag_1" in featured.columns
    assert "alert_count_lag_2" in featured.columns
    assert pd.isna(featured["alert_count_lag_2"].iloc[0])


def test_build_features_drops_initial_nan_rows() -> None:
    """Feature matrix removes rows without full lag history."""
    df = _hourly_frame(list(range(30)))
    featured = build_features(
        df=df,
        target_column="alert_count",
        lags=[1, 24],
        drop_na=True,
    )

    assert len(featured) == len(df) - 24
    assert featured.isna().sum().sum() == 0


def test_build_features_missing_target_raises() -> None:
    """Missing target column raises ValueError."""
    df = pd.DataFrame({"value": [1, 2, 3]})
    with pytest.raises(ValueError, match="Target column"):
        build_features(df=df, target_column="alert_count")
