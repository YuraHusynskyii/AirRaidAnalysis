"""Tests for retrain monitoring and metric degradation alerts."""

from __future__ import annotations

from pathlib import Path

import pytest
from sklearn.linear_model import LinearRegression

from src.config import AppConfig
from src.monitoring import (
    detect_metric_degradation,
    load_metrics_history,
    normalize_artifact_metrics,
    run_monitoring_check,
)
from src.registry import (
    list_model_versions,
    load_model_metadata,
    load_previous_model_metadata,
    save_model_artifact,
)


def test_normalize_artifact_metrics_supports_tuning_payload() -> None:
    """Tuning metrics with best_* keys are normalized."""
    metrics = normalize_artifact_metrics(
        {"best_mae": 0.2, "best_rmse": 0.3, "best_mape": 5.0}
    )
    assert metrics["mae"] == pytest.approx(0.2)


def test_detect_metric_degradation_flags_relative_increase() -> None:
    """Relative MAE increase above threshold creates an alert."""
    alerts = detect_metric_degradation(
        previous_metrics={"mae": 0.10, "rmse": 0.12, "mape": 1.0},
        current_metrics={"mae": 0.20, "rmse": 0.12, "mape": 1.0},
        threshold=0.15,
    )
    assert len(alerts) == 1
    assert alerts[0].metric == "mae"


def test_run_monitoring_check_persists_history_and_alerts(tmp_path: Path) -> None:
    """Monitoring writes history and alert files after retrain comparison."""
    model = LinearRegression()
    model.fit([[1.0], [2.0]], [1.0, 2.0])
    save_model_artifact(
        model=model,
        model_name="prod_model",
        registry_dir=tmp_path,
        metrics={"mae": 0.10, "rmse": 0.12, "mape": 1.0},
        feature_columns=["hour"],
    )
    save_model_artifact(
        model=model,
        model_name="prod_model",
        registry_dir=tmp_path,
        metrics={"mae": 0.20, "rmse": 0.12, "mape": 1.0},
        feature_columns=["hour"],
    )

    previous = load_previous_model_metadata(
        model_name="prod_model",
        registry_dir=tmp_path,
    )
    current = load_model_metadata(
        model_name="prod_model",
        version=list_model_versions("prod_model", tmp_path)[0],
        registry_dir=tmp_path,
    )
    config = AppConfig(
        monitoring_history_path=tmp_path / "history.json",
        monitoring_alerts_path=tmp_path / "alerts.json",
        monitoring_degradation_threshold=0.15,
    )

    result = run_monitoring_check(
        model_name="prod_model",
        current_metadata=current,
        previous_metadata=previous,
        config=config,
    )

    assert len(result.alerts) == 1
    assert config.monitoring_history_path.exists()
    assert config.monitoring_alerts_path.exists()
    assert len(load_metrics_history(config.monitoring_history_path)) == 1
