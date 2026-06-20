"""Sliding-window rate limiting middleware for the inference API."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from time import monotonic
from typing import Callable, Protocol

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from src.metrics import record_rate_limit_exceeded


class RateLimiterBackend(Protocol):
    """Protocol for interchangeable rate limiter backends."""

    def check(self, key: str) -> RateLimitDecision:
        """Evaluate one request for the given client key."""


def create_rate_limiter(
    *,
    backend: str,
    max_requests: int,
    window_seconds: float,
    redis_url: str | None = None,
    redis_key_prefix: str = "airraid:ratelimit",
) -> RateLimiterBackend:
    """Build in-memory or Redis-backed rate limiter.

    Args:
        backend: ``memory`` or ``redis``.
        max_requests: Maximum allowed requests per window.
        window_seconds: Window size in seconds.
        redis_url: Redis URL when ``backend=redis``.
        redis_key_prefix: Redis key prefix for shared limiter keys.

    Returns:
        RateLimiterBackend: Configured limiter instance.

    Raises:
        ValueError: If backend or redis_url configuration is invalid.
        RuntimeError: If Redis limiter initialization fails.
    """
    normalized = backend.strip().lower()
    if normalized == "memory":
        return SlidingWindowRateLimiter(
            max_requests=max_requests,
            window_seconds=window_seconds,
        )
    if normalized == "redis":
        if not redis_url:
            raise ValueError("redis_url is required when serving_rate_limit_backend=redis.")
        from src.redis_rate_limit import build_redis_rate_limiter

        return build_redis_rate_limiter(
            redis_url=redis_url,
            max_requests=max_requests,
            window_seconds=window_seconds,
            key_prefix=redis_key_prefix,
        )
    raise ValueError(f"Unsupported rate limit backend: {backend}")


@dataclass(frozen=True)
class RateLimitDecision:
    """Outcome of a rate-limit check for one client."""

    allowed: bool
    remaining: int
    retry_after_seconds: int
    limit: int
    window_seconds: float


class SlidingWindowRateLimiter:
    """In-memory sliding-window rate limiter keyed by client identifier."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        """Initialize limiter state.

        Args:
            max_requests: Maximum allowed requests per window.
            window_seconds: Window size in seconds.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque[float]:
        """Drop request timestamps outside the active window."""
        window = self._requests[key]
        while window and now - window[0] >= self.window_seconds:
            window.popleft()
        return window

    def check(self, key: str) -> RateLimitDecision:
        """Evaluate and record one request for the given client key.

        Args:
            key: Client identifier, typically remote IP.

        Returns:
            RateLimitDecision: Allow/deny decision with header metadata.
        """
        now = monotonic()
        window = self._prune(key, now)

        if len(window) >= self.max_requests:
            retry_after = max(
                1,
                int(self.window_seconds - (now - window[0])) + 1,
            )
            return RateLimitDecision(
                allowed=False,
                remaining=0,
                retry_after_seconds=retry_after,
                limit=self.max_requests,
                window_seconds=self.window_seconds,
            )

        window.append(now)
        remaining = max(0, self.max_requests - len(window))
        return RateLimitDecision(
            allowed=True,
            remaining=remaining,
            retry_after_seconds=0,
            limit=self.max_requests,
            window_seconds=self.window_seconds,
        )


def build_rate_limit_headers(decision: RateLimitDecision) -> dict[str, str]:
    """Build standard rate-limit response headers.

    Args:
        decision: Rate-limit decision for the current request.

    Returns:
        dict[str, str]: Header mapping for clients and proxies.
    """
    headers = {
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(decision.remaining),
        "X-RateLimit-Window-Seconds": str(int(decision.window_seconds)),
    }
    if not decision.allowed:
        headers["Retry-After"] = str(decision.retry_after_seconds)
    return headers


def default_client_key(request: Request) -> str:
    """Resolve a stable client key from the incoming request.

    Args:
        request: Incoming HTTP request.

    Returns:
        str: Client identifier used for rate limiting.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware that returns HTTP 429 when limits are exceeded."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        enabled: bool,
        max_requests: int,
        window_seconds: float,
        exempt_paths: set[str] | None = None,
        client_key_resolver: Callable[[Request], str] | None = None,
        limiter: RateLimiterBackend | None = None,
    ) -> None:
        """Configure middleware limits and exemptions.

        Args:
            app: ASGI application.
            enabled: Whether rate limiting is active.
            max_requests: Allowed requests per client per window.
            window_seconds: Sliding window size in seconds.
            exempt_paths: Paths that bypass rate limiting (e.g. health probes).
            client_key_resolver: Optional custom client key function.
            limiter: Optional pre-built limiter backend instance.
        """
        super().__init__(app)
        self.enabled = enabled
        self.exempt_paths = exempt_paths or {"/health"}
        self.client_key_resolver = client_key_resolver or default_client_key
        self.limiter = limiter or SlidingWindowRateLimiter(
            max_requests=max_requests,
            window_seconds=window_seconds,
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        """Apply rate limiting before delegating to route handlers."""
        if not self.enabled or request.url.path in self.exempt_paths:
            return await call_next(request)

        decision = self.limiter.check(self.client_key_resolver(request))
        if not decision.allowed:
            record_rate_limit_exceeded()
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too Many Requests. Rate limit exceeded.",
                    "retry_after_seconds": decision.retry_after_seconds,
                },
                headers=build_rate_limit_headers(decision),
            )

        response = await call_next(request)
        for header_name, header_value in build_rate_limit_headers(decision).items():
            response.headers[header_name] = header_value
        return response
