"""Tests for regional preprocessing and evaluation."""

from __future__ import annotations

import pandas as pd

from src.baseline import evaluate_regional_models
from src.preprocessing import resample_regional_alert_counts


def _indexed_alerts() -> pd.DataFrame:
    timestamps = pd.to_datetime(
        [
            "2024-06-01 10:00",
            "2024-06-01 11:00",
            "2024-06-01 10:00",
            "2024-06-01 12:00",
            "2024-06-02 10:00",
            "2024-06-02 11:00",
        ]
    )
    return pd.DataFrame(
        {
            "region": ["Kyiv", "Kyiv", "Lviv", "Lviv", "Kyiv", "Lviv"],
        },
        index=timestamps,
    )


def test_resample_regional_alert_counts_shape() -> None:
    """Regional resample returns one column per region."""
    regional_df = resample_regional_alert_counts(
        df=_indexed_alerts(),
        region_column="region",
        rule="1h",
    )

    assert set(regional_df.columns) == {"Kyiv", "Lviv"}
    assert regional_df.loc["2024-06-01 10:00", "Kyiv"] == 1.0
    assert regional_df.loc["2024-06-01 10:00", "Lviv"] == 1.0


def test_evaluate_regional_models() -> None:
    """Regional evaluation returns metrics keyed by region and model."""
    index = pd.date_range("2024-06-01", periods=40, freq="h")
    regional_df = pd.DataFrame(
        {
            "Kyiv": (index.hour % 5).astype(float),
            "Lviv": (index.hour % 7).astype(float),
        },
        index=index,
    )
    metrics = evaluate_regional_models(
        regional_df=regional_df,
        target_column="alert_count",
        test_size=0.2,
        season_period=4,
        lag_periods=[1, 4],
        random_seed=42,
        n_estimators=20,
    )

    assert "Kyiv" in metrics
    assert "Lviv" in metrics
    assert "seasonal_naive" in metrics["Kyiv"]
    assert "lightgbm" in metrics["Kyiv"]
