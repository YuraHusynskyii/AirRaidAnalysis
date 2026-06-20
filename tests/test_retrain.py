"""Tests for scheduled retraining workflow."""

from __future__ import annotations

from pathlib import Path

from src.config import AppConfig
from src.registry import load_latest_model_artifact
from src.retrain import run_retrain


def test_run_retrain_registers_model(tmp_path: Path) -> None:
    """Retrain workflow saves a production model artifact."""
    config = AppConfig(
        raw_data_path=Path("data/raw/alerts.csv"),
        processed_data_path=tmp_path / "processed.csv",
        features_data_path=tmp_path / "features.csv",
        baseline_metrics_path=tmp_path / "metrics.json",
        summary_report_path=tmp_path / "summary.md",
        model_registry_dir=tmp_path / "models",
        production_model_name="xgboost_global",
        enable_tuning=False,
    )

    artifact_dir = run_retrain(config=config)
    model, metadata = load_latest_model_artifact(
        model_name="xgboost_global",
        registry_dir=tmp_path / "models",
    )

    assert artifact_dir.exists()
    assert metadata["model_name"] == "xgboost_global"
    assert "metrics" in metadata
    assert model is not None
