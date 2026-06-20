"""Tests for API key authentication middleware."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sklearn.linear_model import LinearRegression
from starlette.requests import Request

from src.auth import extract_api_key
from src.config import AppConfig
from src.registry import save_model_artifact
from src.serving import create_app


def _build_request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/models/test",
        "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
    }
    return Request(scope)


def test_extract_api_key_from_x_api_key_header() -> None:
    """Extractor reads X-API-Key header."""
    request = _build_request({"X-API-Key": "secret"})
    assert extract_api_key(request) == "secret"


def test_extract_api_key_from_bearer_authorization() -> None:
    """Extractor reads Authorization Bearer token."""
    request = _build_request({"Authorization": "Bearer secret-token"})
    assert extract_api_key(request) == "secret-token"


def test_api_key_middleware_returns_401_without_key(tmp_path) -> None:
    """Protected routes return HTTP 401 when API key is missing."""
    model = LinearRegression()
    model.fit([[1.0], [2.0]], [1.0, 2.0])
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
        serving_api_key_enabled=True,
        serving_api_key="super-secret",
        serving_rate_limit_enabled=False,
    )
    client = TestClient(create_app(config=config))

    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 200

    unauthorized = client.get("/v1/models/test_model")
    assert unauthorized.status_code == 401
    assert unauthorized.json()["detail"] == "Invalid or missing API key."
    assert unauthorized.headers["WWW-Authenticate"] == "Bearer"


def test_api_key_middleware_allows_valid_key(tmp_path) -> None:
    """Valid API key grants access to protected routes."""
    model = LinearRegression()
    model.fit([[1.0], [2.0]], [1.0, 2.0])
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
        serving_api_key_enabled=True,
        serving_api_key="super-secret",
        serving_rate_limit_enabled=False,
    )
    client = TestClient(create_app(config=config))

    response = client.get(
        "/v1/models/test_model",
        headers={"X-API-Key": "super-secret"},
    )
    assert response.status_code == 200
