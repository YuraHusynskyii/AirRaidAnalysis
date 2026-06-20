"""HTTP middleware for Prometheus request metrics."""

from __future__ import annotations

from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from src.metrics import record_http_request


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """Collect request count and latency metrics for Prometheus scraping."""

    def __init__(self, app: ASGIApp, *, enabled: bool = True) -> None:
        """Configure metrics middleware.

        Args:
            app: ASGI application.
            enabled: Whether metrics collection is active.
        """
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next) -> Response:
        """Measure and record one HTTP request."""
        if not self.enabled:
            return await call_next(request)

        started = perf_counter()
        response = await call_next(request)
        duration = perf_counter() - started
        record_http_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_seconds=duration,
        )
        return response
