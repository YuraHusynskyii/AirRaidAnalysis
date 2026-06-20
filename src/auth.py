"""API key authentication middleware for the inference API."""

from __future__ import annotations

import secrets
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from src.metrics import record_auth_failure


def extract_api_key(request: Request) -> str | None:
    """Extract API key from supported request headers.

    Supported headers:
    - ``X-API-Key``
    - ``Authorization: Bearer <token>``

    Args:
        request: Incoming HTTP request.

    Returns:
        str | None: Provided API key, if any.
    """
    header_key = request.headers.get("x-api-key")
    if header_key:
        return header_key.strip()

    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def is_valid_api_key(provided_key: str, valid_keys: set[str]) -> bool:
    """Check whether provided key matches any valid rotated key."""
    for expected_key in valid_keys:
        if secrets.compare_digest(provided_key, expected_key):
            return True
    return False


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces API key auth and returns HTTP 401 on failure."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        enabled: bool,
        valid_api_keys: set[str] | None = None,
        api_key: str | None = None,
        exempt_paths: set[str] | None = None,
        key_extractor: Callable[[Request], str | None] | None = None,
    ) -> None:
        """Configure API key authentication.

        Args:
            app: ASGI application.
            enabled: Whether auth enforcement is active.
            valid_api_keys: Set of currently valid API keys (rotation-aware).
            api_key: Legacy single-key configuration fallback.
            exempt_paths: Paths that bypass authentication.
            key_extractor: Optional custom API key extractor.
        """
        super().__init__(app)
        self.enabled = enabled
        keys = set(valid_api_keys or [])
        if api_key:
            keys.add(api_key)
        self.valid_api_keys = keys
        self.exempt_paths = exempt_paths or {"/health", "/metrics"}
        self.key_extractor = key_extractor or extract_api_key

    async def dispatch(self, request: Request, call_next) -> Response:
        """Validate API key before delegating to downstream handlers."""
        if not self.enabled or request.url.path in self.exempt_paths:
            return await call_next(request)

        if not self.valid_api_keys:
            return JSONResponse(
                status_code=503,
                content={"detail": "API key auth enabled but no key configured."},
            )

        provided_key = self.key_extractor(request)
        if not provided_key or not is_valid_api_key(provided_key, self.valid_api_keys):
            record_auth_failure()
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key."},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
