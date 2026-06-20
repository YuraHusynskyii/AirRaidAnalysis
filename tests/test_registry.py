"""Tests for model registry persistence."""

from __future__ import annotations

import pytest
from sklearn.linear_model import LinearRegression

from src.registry import load_latest_model_artifact, save_model_artifact


def test_save_and_load_latest_model_artifact(tmp_path) -> None:
    """Registry can persist and reload latest model artifact."""
    model = LinearRegression()
    model.fit([[1.0], [2.0], [3.0]], [1.0, 2.0, 3.0])

    artifact_dir = save_model_artifact(
        model=model,
        model_name="test_model",
        registry_dir=tmp_path,
        metrics={"mae": 0.1, "rmse": 0.2, "mape": 1.0},
        feature_columns=["hour"],
        metadata={"source": "unit-test"},
    )

    loaded_model, metadata = load_latest_model_artifact(
        model_name="test_model",
        registry_dir=tmp_path,
    )

    assert artifact_dir.exists()
    assert metadata["metrics"]["mae"] == 0.1
    assert loaded_model.predict([[4.0]])[0] == pytest.approx(4.0)
