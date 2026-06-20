"""Tests for baseline forecasting models."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.baseline import (
    evaluate_seasonal_naive,
    seasonal_naive_forecast,
    time_series_train_test_split,
)


def _seasonal_series(length: int, season: int = 4) -> pd.Series:
    values = np.tile(np.array([1.0, 2.0, 3.0, 4.0]), length // season + 1)[:length]
    index = pd.date_range("2024-06-01", periods=length, freq="h")
    return pd.Series(values, index=index, name="alert_count")


def test_time_series_train_test_split_preserves_order() -> None:
    """Chronological split keeps train before test."""
    series = _seasonal_series(20)
    train, test = time_series_train_test_split(series, test_size=0.2)

    assert len(train) == 16
    assert len(test) == 4
    assert train.index.max() < test.index.min()


def test_seasonal_naive_forecast_repeats_pattern() -> None:
    """Seasonal naive returns values from the previous seasonal cycle."""
    series = _seasonal_series(12, season=4)
    horizon = series.index[-4:]
    history = series.iloc[:-4]

    forecast = seasonal_naive_forecast(
        history=history,
        horizon_index=horizon,
        season_period=4,
    )

    expected = series.iloc[-8:-4].to_numpy()
    np.testing.assert_allclose(forecast.to_numpy(), expected)


def test_evaluate_seasonal_naive_returns_metrics() -> None:
    """Baseline evaluation returns standard regression metrics."""
    series = _seasonal_series(40, season=4)
    metrics = evaluate_seasonal_naive(
        series=series,
        test_size=0.2,
        season_period=4,
    )

    assert {"mae", "rmse", "mape"} == set(metrics.keys())
    assert metrics["mae"] == pytest.approx(0.0)
    assert metrics["rmse"] == pytest.approx(0.0)


def test_seasonal_naive_forecast_short_history_raises() -> None:
    """Insufficient history for seasonal lag raises ValueError."""
    series = _seasonal_series(3, season=4)
    with pytest.raises(ValueError, match="shorter than season_period"):
        seasonal_naive_forecast(
            history=series,
            horizon_index=series.index,
            season_period=4,
        )
