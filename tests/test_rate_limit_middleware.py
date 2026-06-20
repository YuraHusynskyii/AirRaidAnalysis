"""Tests for inference API rate-limit middleware."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sklearn.linear_model import LinearRegression

from src.config import AppConfig
from src.rate_limit import SlidingWindowRateLimiter
from src.registry import save_model_artifact
from src.serving import create_app


def test_sliding_window_rate_limiter_blocks_after_limit() -> None:
    """Limiter denies requests once the window capacity is reached."""
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60.0)

    first = limiter.check("client-a")
    second = limiter.check("client-a")
    third = limiter.check("client-a")

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.remaining == 0
    assert third.retry_after_seconds >= 1


def test_rate_limit_middleware_returns_429_with_headers(tmp_path) -> None:
    """Exceeded limits return HTTP 429 and standard rate-limit headers."""
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
        serving_rate_limit_enabled=True,
        serving_rate_limit_requests=2,
        serving_rate_limit_window_seconds=60.0,
        serving_rate_limit_exempt_paths=["/health"],
    )
    client = TestClient(create_app(config=config))

    assert client.get("/health").status_code == 200

    first = client.get("/v1/models/test_model")
    second = client.get("/v1/models/test_model")
    blocked = client.get("/v1/models/test_model")

    assert first.status_code == 200
    assert second.status_code == 200
    assert "X-RateLimit-Remaining" in first.headers

    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too Many Requests. Rate limit exceeded."
    assert blocked.headers["Retry-After"]
    assert blocked.headers["X-RateLimit-Remaining"] == "0"


def test_rate_limit_can_be_disabled(tmp_path) -> None:
    """Disabled middleware does not block repeated requests."""
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
        serving_rate_limit_enabled=False,
        serving_rate_limit_requests=1,
    )
    client = TestClient(create_app(config=config))

    for _ in range(3):
        response = client.get("/v1/models/test_model")
        assert response.status_code == 200
