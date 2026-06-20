"""Production readiness API sanity checks for auth, rate limiting, and health probes."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sklearn.linear_model import LinearRegression

from src.config import AppConfig
from src.registry import save_model_artifact
from src.serving import create_app


def _build_verification_client(
    tmp_path,
    *,
    api_key_enabled: bool = True,
    rate_limit_requests: int = 3,
) -> TestClient:
    """Create a test client with auth + tight rate limits for verification."""
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
        serving_api_key_enabled=api_key_enabled,
        serving_api_key="audit-test-key",
        serving_rate_limit_enabled=True,
        serving_rate_limit_requests=rate_limit_requests,
        serving_rate_limit_window_seconds=60.0,
        serving_rate_limit_exempt_paths=["/health", "/metrics"],
    )
    return TestClient(create_app(config=config))


def test_health_is_exempt_from_rate_limit_config() -> None:
    """Default config keeps /health outside rate-limit enforcement."""
    config = AppConfig()
    assert "/health" in config.serving_rate_limit_exempt_paths


def test_unauthorized_without_api_key(tmp_path) -> None:
    """Protected routes return HTTP 401 when API key is missing."""
    client = _build_verification_client(tmp_path)

    response = client.get("/v1/models/test_model")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key."
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_rate_limit_returns_429_after_burst(tmp_path) -> None:
    """Repeated authenticated requests return HTTP 429 once limit is exceeded."""
    client = _build_verification_client(tmp_path, rate_limit_requests=2)
    headers = {"X-API-Key": "audit-test-key"}

    first = client.get("/v1/models/test_model", headers=headers)
    second = client.get("/v1/models/test_model", headers=headers)
    blocked = client.get("/v1/models/test_model", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too Many Requests. Rate limit exceeded."
    assert blocked.headers["Retry-After"]
    assert blocked.headers["X-RateLimit-Remaining"] == "0"


def test_health_stays_200_during_rate_limit(tmp_path) -> None:
    """Health probe stays available even when inference routes are throttled."""
    client = _build_verification_client(tmp_path, rate_limit_requests=1)
    headers = {"X-API-Key": "audit-test-key"}

    assert client.get("/v1/models/test_model", headers=headers).status_code == 200
    assert client.get("/v1/models/test_model", headers=headers).status_code == 429

    for _ in range(5):
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"


def test_combined_auth_and_rate_limit_matrix(tmp_path) -> None:
    """End-to-end matrix: 401 without key, 429 on burst, 200 health throughout."""
    client = _build_verification_client(tmp_path, rate_limit_requests=2)

    assert client.get("/v1/models/test_model").status_code == 401

    headers = {"X-API-Key": "audit-test-key"}
    assert client.get("/v1/models/test_model", headers=headers).status_code == 200
    assert client.get("/v1/models/test_model", headers=headers).status_code == 200
    assert client.get("/v1/models/test_model", headers=headers).status_code == 429
    assert client.get("/health").status_code == 200
