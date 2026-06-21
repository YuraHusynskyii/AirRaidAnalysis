"""Tests for tuned model auto-registration."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.config import AppConfig
from src.registry import load_latest_model_artifact
from src.retrain import run_retrain


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


def test_run_retrain_registers_tuned_model_when_enabled(tmp_path: Path, monkeypatch) -> None:
    """Retrain registers Optuna-tuned model when tuning is enabled."""
    config = AppConfig(
        raw_data_path=Path("data/samples/sample_alerts.csv"),
        processed_data_path=tmp_path / "processed.csv",
        features_data_path=tmp_path / "features.csv",
        baseline_metrics_path=tmp_path / "metrics.json",
        summary_report_path=tmp_path / "summary.md",
        tuning_results_path=tmp_path / "tuning.json",
        model_registry_dir=tmp_path / "models",
        production_model_name="xgboost_global",
        enable_tuning=True,
        tuning_trials=2,
        auto_register_tuned_model=True,
    )

    def _fake_pipeline(config=None):
        index = pd.date_range("2024-06-01", periods=65, freq="h")
        processed = pd.DataFrame({"alert_count": range(65)}, index=index)
        featured = _featured_frame()
        regional = pd.DataFrame({"Kyiv": range(65)}, index=index)
        return processed, featured, regional

    monkeypatch.setattr("src.retrain.run_pipeline", _fake_pipeline)
    monkeypatch.setattr("src.retrain.run_baseline_evaluation", lambda **kwargs: {})

    artifact_dir = run_retrain(config=config)
    _, metadata = load_latest_model_artifact(
        model_name="xgboost_global",
        registry_dir=tmp_path / "models",
    )

    assert artifact_dir.exists()
    assert metadata["metadata"]["tuned"] is True
    assert "best_params" in metadata["metadata"]
