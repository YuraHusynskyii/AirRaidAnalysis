"""Tests for model A/B evaluation helpers."""

from __future__ import annotations

import json
from pathlib import Path

from sklearn.linear_model import LinearRegression

from src.evaluation import (
    compare_model_metrics,
    compare_registry_model_versions,
    evaluate_models_ab_on_holdout,
    save_ab_evaluation_report,
)
from src.registry import save_model_artifact


def test_compare_model_metrics_picks_lower_mae_winner() -> None:
    """Winner is model with lower primary metric."""
    report = compare_model_metrics(
        metrics_a={"mae": 0.10, "rmse": 0.2, "mape": 1.0},
        metrics_b={"mae": 0.20, "rmse": 0.3, "mape": 2.0},
        label_a="candidate_a",
        label_b="candidate_b",
        primary_metric="mae",
    )
    assert report["winner"] == "candidate_a"


def test_compare_registry_model_versions(tmp_path: Path) -> None:
    """Registry metadata comparison selects better artifact version."""
    model = LinearRegression()
    model.fit([[1.0], [2.0]], [1.0, 2.0])

    first = save_model_artifact(
        model=model,
        model_name="prod",
        registry_dir=tmp_path,
        metrics={"mae": 0.20, "rmse": 0.3, "mape": 2.0},
        feature_columns=["hour"],
    )
    second = save_model_artifact(
        model=model,
        model_name="prod",
        registry_dir=tmp_path,
        metrics={"mae": 0.10, "rmse": 0.2, "mape": 1.0},
        feature_columns=["hour"],
    )

    version_new = second.name
    version_old = first.name
    report = compare_registry_model_versions(
        model_name="prod",
        version_a=version_new,
        version_b=version_old,
        registry_dir=tmp_path,
    )
    assert report["winner"] == f"prod@{version_new}"


def test_evaluate_models_ab_on_holdout(tmp_path: Path) -> None:
    """Holdout A/B evaluation returns winner on synthetic features."""
    import pandas as pd

    index = pd.date_range("2024-01-01", periods=20, freq="h")
    featured = pd.DataFrame(
        {
            "alert_count": range(20),
            "hour": index.hour,
            "day_of_week": index.dayofweek,
            "is_weekend": 0,
        },
        index=index,
    )

    model_a = LinearRegression()
    model_b = LinearRegression()
    model_a.fit(featured[["hour"]], featured["alert_count"])
    model_b.fit(featured[["hour"]], featured["alert_count"] * 0)

    report = evaluate_models_ab_on_holdout(
        featured_df=featured,
        model_a=model_a,
        model_b=model_b,
        feature_columns=["hour"],
        target_column="alert_count",
        test_size=0.2,
        label_a="hour_model",
        label_b="dow_model",
    )
    assert report["evaluation_type"] == "holdout_ab"
    assert report["winner"] in {"hour_model", "dow_model", "tie"}


def test_save_ab_evaluation_report(tmp_path: Path) -> None:
    """A/B report is persisted as JSON."""
    report = compare_model_metrics(
        metrics_a={"mae": 0.1, "rmse": 0.2, "mape": 1.0},
        metrics_b={"mae": 0.2, "rmse": 0.3, "mape": 2.0},
        label_a="a",
        label_b="b",
    )
    path = save_ab_evaluation_report(report, tmp_path / "ab.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["winner"] == "a"
