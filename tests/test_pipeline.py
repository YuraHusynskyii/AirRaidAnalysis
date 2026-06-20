"""End-to-end pipeline smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.config import AppConfig
from src.main import run_baseline_evaluation, run_pipeline


def test_run_pipeline_smoke(tmp_path: Path) -> None:
    """Pipeline loads fixture CSV and writes processed hourly counts."""
    raw_path = Path("data/raw/alerts.csv")
    processed_path = tmp_path / "alerts_processed.csv"
    features_path = tmp_path / "alerts_features.csv"

    config = AppConfig(
        raw_data_path=raw_path,
        processed_data_path=processed_path,
        features_data_path=features_path,
    )
    processed_df, featured_df, regional_df = run_pipeline(config=config)

    assert processed_path.exists()
    assert features_path.exists()
    assert "alert_count" in processed_df.columns
    assert len(processed_df) > 0
    assert processed_df["alert_count"].sum() == 55
    assert len(featured_df) > 0
    assert len(regional_df.columns) == 5

    saved_features = pd.read_csv(features_path, index_col=0, parse_dates=True)
    assert {"hour", "day_of_week", "alert_count_lag_1"}.issubset(saved_features.columns)

    saved_df = pd.read_csv(processed_path, index_col=0, parse_dates=True)
    assert len(saved_df) == len(processed_df)


def test_run_baseline_evaluation_smoke(tmp_path: Path) -> None:
    """Baseline evaluation returns metrics and writes JSON/Markdown reports."""
    raw_path = Path("data/raw/alerts.csv")
    metrics_path = tmp_path / "baseline_metrics.json"
    summary_path = tmp_path / "evaluation_summary.md"
    config = AppConfig(
        raw_data_path=raw_path,
        processed_data_path=tmp_path / "alerts_processed.csv",
        features_data_path=tmp_path / "alerts_features.csv",
        baseline_metrics_path=metrics_path,
        summary_report_path=summary_path,
        test_size=0.2,
        season_period=24,
    )
    processed_df, featured_df, regional_df = run_pipeline(config=config)
    metrics = run_baseline_evaluation(
        processed_df=processed_df,
        featured_df=featured_df,
        regional_df=regional_df,
        config=config,
    )

    assert metrics_path.exists()
    assert summary_path.exists()
    saved_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert set(metrics.keys()) == {"global", "regional"}
    assert set(metrics["global"].keys()) == {
        "seasonal_naive",
        "linear_regression",
        "arima",
        "sarimax_s24",
        "xgboost",
        "lightgbm",
    }
    assert saved_metrics == metrics
    assert len(metrics["regional"]) > 0
    assert "lightgbm" in next(iter(metrics["regional"].values()))
    assert "Global Baselines" in summary_path.read_text(encoding="utf-8")
