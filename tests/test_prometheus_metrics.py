"""Tests for Prometheus metrics endpoint and instrumentation."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sklearn.linear_model import LinearRegression

from src.config import AppConfig
from src.registry import save_model_artifact
from src.serving import create_app


def test_metrics_endpoint_exposes_prometheus_format(tmp_path) -> None:
    """GET /metrics returns Prometheus text exposition."""
    config = AppConfig(
        serving_metrics_enabled=True,
        serving_rate_limit_enabled=False,
    )
    client = TestClient(create_app(config=config))

    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "airraid_http_requests_total" in response.text


def test_predict_increments_prediction_counter(tmp_path) -> None:
    """Successful predict requests increment airraid_predictions_total."""
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
        serving_rate_limit_enabled=False,
        serving_metrics_enabled=True,
    )
    client = TestClient(create_app(config=config))

    predict_response = client.post(
        "/v1/predict",
        json={"features": {"hour": 4.0}},
    )
    assert predict_response.status_code == 200

    metrics_response = client.get("/metrics")
    assert 'airraid_predictions_total{model_name="test_model"}' in metrics_response.text
