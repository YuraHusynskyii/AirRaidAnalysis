"""Tests for FastAPI inference service."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sklearn.linear_model import LinearRegression

from src.config import AppConfig
from src.registry import save_model_artifact
from src.serving import create_app, predict_batch_from_features, predict_from_features


def test_predict_from_features_validates_columns() -> None:
    """Missing feature columns raise ValueError."""
    model = LinearRegression()
    model.fit([[1.0], [2.0]], [1.0, 2.0])

    with pytest.raises(ValueError, match="Missing feature columns"):
        predict_from_features(
            model=model,
            feature_columns=["hour"],
            features={},
        )


def test_serving_predict_and_metadata(tmp_path: Path) -> None:
    """Serving API returns metadata and predictions for registered models."""
    model = LinearRegression()
    model.fit([[1.0], [2.0], [3.0]], [1.0, 2.0, 3.0])
    save_model_artifact(
        model=model,
        model_name="test_model",
        registry_dir=tmp_path,
        metrics={"mae": 0.1, "rmse": 0.2, "mape": 1.0},
        feature_columns=["hour"],
        metadata={"source": "unit-test"},
    )

    config = AppConfig(
        model_registry_dir=tmp_path,
        production_model_name="test_model",
    )
    client = TestClient(create_app(config=config))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    metadata = client.get("/v1/models/test_model")
    assert metadata.status_code == 200
    assert metadata.json()["feature_columns"] == ["hour"]

    response = client.post(
        "/v1/predict",
        json={"features": {"hour": 4.0}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model_name"] == "test_model"
    assert body["prediction"] == pytest.approx(4.0)


def test_serving_predict_missing_model_returns_404(tmp_path: Path) -> None:
    """Unknown model name returns HTTP 404."""
    config = AppConfig(
        model_registry_dir=tmp_path,
        production_model_name="missing_model",
    )
    client = TestClient(create_app(config=config))

    response = client.post(
        "/v1/predict",
        json={"features": {"hour": 1.0}},
    )
    assert response.status_code == 404


def test_serving_batch_predict_with_regions(tmp_path: Path) -> None:
    """Batch endpoint returns regional predictions in request order."""
    model = LinearRegression()
    model.fit([[1.0], [2.0], [3.0]], [1.0, 2.0, 3.0])
    save_model_artifact(
        model=model,
        model_name="test_model",
        registry_dir=tmp_path,
        metrics={"mae": 0.1, "rmse": 0.2, "mape": 1.0},
        feature_columns=["hour"],
    )

    config = AppConfig(
        model_registry_dir=tmp_path,
        production_model_name="test_model",
    )
    client = TestClient(create_app(config=config))

    response = client.post(
        "/v1/predict/batch",
        json={
            "items": [
                {"region": "Kyiv", "features": {"hour": 2.0}},
                {"region": "Lviv", "features": {"hour": 5.0}},
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["region"] == "Kyiv"
    assert body["items"][0]["prediction"] == pytest.approx(2.0)
    assert body["items"][1]["prediction"] == pytest.approx(5.0)


def test_predict_batch_from_features(tmp_path: Path) -> None:
    """Batch helper validates rows and returns aligned predictions."""
    model = LinearRegression()
    model.fit([[1.0], [2.0]], [1.0, 2.0])

    predictions = predict_batch_from_features(
        model=model,
        feature_columns=["hour"],
        feature_rows=[{"hour": 3.0}, {"hour": 4.0}],
    )
    assert predictions == [pytest.approx(3.0), pytest.approx(4.0)]
