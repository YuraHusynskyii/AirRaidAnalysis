"""Tracing middleware for HTTP request spans."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from src.tracing import set_span_attributes, trace_span


class TracingMiddleware(BaseHTTPMiddleware):
    """Create one OpenTelemetry span per incoming HTTP request."""

    def __init__(self, app: ASGIApp, *, enabled: bool = True) -> None:
        """Configure tracing middleware.

        Args:
            app: ASGI application.
            enabled: Whether request spans should be created.
        """
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next) -> Response:
        """Wrap request handling in a tracing span."""
        if not self.enabled:
            return await call_next(request)

        with trace_span(
            "http.request",
            attributes={
                "http.method": request.method,
                "http.target": request.url.path,
            },
        ):
            response = await call_next(request)
            set_span_attributes({"http.status_code": str(response.status_code)})
            return response
