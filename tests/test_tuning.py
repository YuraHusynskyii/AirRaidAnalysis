"""Tests for Optuna hyperparameter tuning."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.tuning import run_tuning, save_tuning_report, tune_xgboost


def _featured_frame(length: int = 40) -> pd.DataFrame:
    index = pd.date_range("2024-06-01", periods=length, freq="h")
    alert_count = pd.Series(np.linspace(1, 6, num=length), index=index)
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


def test_tune_xgboost_returns_best_params() -> None:
    """XGBoost tuning returns best params and MAE."""
    result = tune_xgboost(
        featured_df=_featured_frame(),
        target_column="alert_count",
        test_size=0.2,
        random_seed=42,
        n_trials=3,
    )
    assert "best_params" in result
    assert result["best_mae"] >= 0.0
    assert result["n_trials"] == 3


def test_run_tuning_smoke(tmp_path) -> None:
    """Combined tuning workflow writes JSON report."""
    featured_df = _featured_frame(length=50)
    series = featured_df["alert_count"]
    results = run_tuning(
        featured_df=featured_df,
        processed_series=series,
        target_column="alert_count",
        test_size=0.2,
        random_seed=42,
        season_period=4,
        n_trials=4,
    )
    report_path = save_tuning_report(results, tmp_path / "tuning_results.json")

    assert "xgboost" in results
    assert "sarimax" in results
    assert report_path.exists()
