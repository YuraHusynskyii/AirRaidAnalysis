"""Tests for model registry version helpers."""

from __future__ import annotations

from sklearn.linear_model import LinearRegression

from src.registry import (
    list_model_versions,
    load_model_metadata,
    load_previous_model_metadata,
    save_model_artifact,
)


def test_list_and_load_previous_model_metadata(tmp_path) -> None:
    """Registry exposes version history and previous artifact metadata."""
    model = LinearRegression()
    model.fit([[1.0], [2.0]], [1.0, 2.0])

    save_model_artifact(
        model=model,
        model_name="test_model",
        registry_dir=tmp_path,
        metrics={"mae": 0.1, "rmse": 0.2, "mape": 1.0},
        feature_columns=["hour"],
        metadata={"version_tag": "v1"},
    )
    save_model_artifact(
        model=model,
        model_name="test_model",
        registry_dir=tmp_path,
        metrics={"mae": 0.2, "rmse": 0.3, "mape": 2.0},
        feature_columns=["hour"],
        metadata={"version_tag": "v2"},
    )

    versions = list_model_versions("test_model", tmp_path)
    assert len(versions) == 2

    previous = load_previous_model_metadata("test_model", tmp_path)
    assert previous is not None
    assert previous["metrics"]["mae"] == 0.1

    latest = load_model_metadata("test_model", versions[0], tmp_path)
    assert latest["metrics"]["mae"] == 0.2
