"""Tests for boosting baselines."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.baseline import evaluate_lightgbm, evaluate_xgboost


def _featured_frame(length: int = 40) -> pd.DataFrame:
    index = pd.date_range("2024-06-01", periods=length, freq="h")
    alert_count = pd.Series(np.linspace(1, 5, num=length), index=index)
    featured = pd.DataFrame(
        {
            "alert_count": alert_count,
            "hour": index.hour,
            "day_of_week": index.dayofweek,
            "alert_count_lag_1": alert_count.shift(1),
        },
        index=index,
    )
    return featured.dropna()


def test_evaluate_xgboost_returns_metrics() -> None:
    """XGBoost baseline returns standard regression metrics."""
    metrics = evaluate_xgboost(
        featured_df=_featured_frame(),
        target_column="alert_count",
        test_size=0.2,
        random_seed=42,
        n_estimators=20,
    )

    assert {"mae", "rmse", "mape"} == set(metrics.keys())
    assert metrics["mae"] >= 0.0


def test_evaluate_lightgbm_returns_metrics() -> None:
    """LightGBM baseline returns standard regression metrics."""
    metrics = evaluate_lightgbm(
        featured_df=_featured_frame(),
        target_column="alert_count",
        test_size=0.2,
        random_seed=42,
        n_estimators=20,
    )

    assert {"mae", "rmse", "mape"} == set(metrics.keys())
    assert metrics["mae"] >= 0.0
