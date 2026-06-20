"""Tests for ARIMA baseline."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.baseline import evaluate_arima


def _trend_series(length: int = 40) -> pd.Series:
    index = pd.date_range("2024-06-01", periods=length, freq="h")
    values = np.linspace(1.0, 4.0, num=length)
    return pd.Series(values, index=index, name="alert_count")


def test_evaluate_arima_returns_metrics() -> None:
    """ARIMA baseline returns standard regression metrics."""
    series = _trend_series()
    metrics = evaluate_arima(series=series, test_size=0.2, order=(1, 0, 0))

    assert {"mae", "rmse", "mape"} == set(metrics.keys())
    assert metrics["mae"] >= 0.0


def test_evaluate_arima_short_train_raises() -> None:
    """Too-short train split for ARIMA order raises ValueError."""
    series = _trend_series(length=5)
    with pytest.raises(ValueError, match="too short"):
        evaluate_arima(series=series, test_size=0.5, order=(1, 0, 0))
