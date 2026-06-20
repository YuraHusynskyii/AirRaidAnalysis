"""Tests for linear regression baseline."""

from __future__ import annotations

import pandas as pd
import pytest

from src.baseline import evaluate_linear_regression, split_feature_matrix


def _featured_frame(length: int = 30) -> pd.DataFrame:
    index = pd.date_range("2024-06-01", periods=length, freq="h")
    alert_count = pd.Series(range(length), index=index, dtype=float)
    return pd.DataFrame(
        {
            "alert_count": alert_count,
            "hour": index.hour,
            "day_of_week": index.dayofweek,
            "alert_count_lag_1": alert_count.shift(1),
        },
        index=index,
    ).dropna()


def test_split_feature_matrix_shapes() -> None:
    """Chronological split returns aligned train and test matrices."""
    featured_df = _featured_frame()
    x_train, y_train, x_test, y_test = split_feature_matrix(
        featured_df=featured_df,
        target_column="alert_count",
        test_size=0.2,
    )

    assert len(x_train) == len(y_train)
    assert len(x_test) == len(y_test)
    assert "alert_count" not in x_train.columns


def test_evaluate_linear_regression_returns_metrics() -> None:
    """Linear regression baseline returns standard regression metrics."""
    featured_df = _featured_frame(length=40)
    metrics = evaluate_linear_regression(
        featured_df=featured_df,
        target_column="alert_count",
        test_size=0.2,
    )

    assert {"mae", "rmse", "mape"} == set(metrics.keys())
    assert metrics["mae"] >= 0.0


def test_split_feature_matrix_missing_target_raises() -> None:
    """Missing target column raises ValueError."""
    featured_df = pd.DataFrame({"hour": [1, 2, 3]})
    with pytest.raises(ValueError, match="Target column"):
        split_feature_matrix(
            featured_df=featured_df,
            target_column="alert_count",
            test_size=0.2,
        )
