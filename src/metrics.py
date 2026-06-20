"""Prometheus metrics registry and HTTP exposition helpers."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "airraid_http_requests_total",
    "Total HTTP requests processed by the inference API.",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "airraid_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
)
PREDICTIONS_TOTAL = Counter(
    "airraid_predictions_total",
    "Total successful inference predictions.",
    ["model_name"],
)
RATE_LIMIT_EXCEEDED_TOTAL = Counter(
    "airraid_rate_limit_exceeded_total",
    "Total requests rejected by rate-limit middleware.",
)
AUTH_FAILURES_TOTAL = Counter(
    "airraid_auth_failures_total",
    "Total requests rejected due to invalid or missing API key.",
)


def render_prometheus_metrics() -> tuple[bytes, str]:
    """Render current metrics in Prometheus text exposition format.

    Returns:
        tuple[bytes, str]: Metric payload and content type.
    """
    return generate_latest(), CONTENT_TYPE_LATEST


def record_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    """Record one HTTP request observation.

    Args:
        method: HTTP method.
        path: Request path.
        status_code: Response status code.
        duration_seconds: Request duration in seconds.
    """
    labels = {"method": method, "path": path, "status": str(status_code)}
    HTTP_REQUESTS_TOTAL.labels(**labels).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration_seconds)


def record_prediction(model_name: str, count: int = 1) -> None:
    """Increment prediction counter for a model."""
    PREDICTIONS_TOTAL.labels(model_name=model_name).inc(count)


def record_rate_limit_exceeded() -> None:
    """Increment rate-limit rejection counter."""
    RATE_LIMIT_EXCEEDED_TOTAL.inc()


def record_auth_failure() -> None:
    """Increment auth failure counter."""
    AUTH_FAILURES_TOTAL.inc()
