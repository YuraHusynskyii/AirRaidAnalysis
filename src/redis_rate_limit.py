"""Redis-backed sliding-window rate limiter for multi-replica serve."""

from __future__ import annotations

import time
from typing import Any, Protocol

from src.rate_limit import RateLimitDecision


class RedisClientProtocol(Protocol):
    """Minimal Redis client surface used by the rate limiter."""

    def zremrangebyscore(self, name: str, minimum: float, maximum: float) -> int:
        """Remove sorted-set members by score range."""

    def zcard(self, name: str) -> int:
        """Return sorted-set cardinality."""

    def zrange(
        self,
        name: str,
        start: int,
        end: int,
        *,
        withscores: bool = False,
    ) -> list[Any]:
        """Return sorted-set range."""

    def zadd(self, name: str, mapping: dict[str, float]) -> int:
        """Add members to sorted set."""

    def expire(self, name: str, seconds: int) -> bool:
        """Set key TTL."""


class RedisSlidingWindowRateLimiter:
    """Shared sliding-window limiter backed by Redis sorted sets."""

    def __init__(
        self,
        client: RedisClientProtocol,
        max_requests: int,
        window_seconds: float,
        key_prefix: str = "airraid:ratelimit",
    ) -> None:
        """Initialize Redis limiter.

        Args:
            client: Redis client instance.
            max_requests: Maximum allowed requests per window.
            window_seconds: Window size in seconds.
            key_prefix: Prefix for per-client Redis keys.
        """
        self.client = client
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix.rstrip(":")

    def _redis_key(self, client_key: str) -> str:
        return f"{self.key_prefix}:{client_key}"

    def check(self, key: str) -> RateLimitDecision:
        """Evaluate and record one request using a Redis sorted set window."""
        now = time.time()
        redis_key = self._redis_key(key)
        window_start = now - self.window_seconds

        self.client.zremrangebyscore(redis_key, 0, window_start)
        current_count = int(self.client.zcard(redis_key))

        if current_count >= self.max_requests:
            oldest = self.client.zrange(redis_key, 0, 0, withscores=True)
            oldest_score = float(oldest[1]) if len(oldest) >= 2 else now
            retry_after = max(1, int(self.window_seconds - (now - oldest_score)) + 1)
            return RateLimitDecision(
                allowed=False,
                remaining=0,
                retry_after_seconds=retry_after,
                limit=self.max_requests,
                window_seconds=self.window_seconds,
            )

        member = f"{now:.6f}"
        self.client.zadd(redis_key, {member: now})
        self.client.expire(redis_key, int(self.window_seconds) + 1)
        updated_count = int(self.client.zcard(redis_key))
        remaining = max(0, self.max_requests - updated_count)

        return RateLimitDecision(
            allowed=True,
            remaining=remaining,
            retry_after_seconds=0,
            limit=self.max_requests,
            window_seconds=self.window_seconds,
        )


def build_redis_rate_limiter(
    redis_url: str,
    max_requests: int,
    window_seconds: float,
    key_prefix: str = "airraid:ratelimit",
    client: RedisClientProtocol | None = None,
) -> RedisSlidingWindowRateLimiter:
    """Create a Redis rate limiter from URL or injected client.

    Args:
        redis_url: Redis connection URL.
        max_requests: Maximum allowed requests per window.
        window_seconds: Window size in seconds.
        key_prefix: Prefix for per-client Redis keys.
        client: Optional Redis client override (testing).

    Returns:
        RedisSlidingWindowRateLimiter: Configured limiter instance.

    Raises:
        RuntimeError: If Redis client initialization fails.
    """
    if client is not None:
        return RedisSlidingWindowRateLimiter(
            client=client,
            max_requests=max_requests,
            window_seconds=window_seconds,
            key_prefix=key_prefix,
        )

    try:
        import redis

        redis_client = redis.from_url(redis_url, decode_responses=True)
        return RedisSlidingWindowRateLimiter(
            client=redis_client,
            max_requests=max_requests,
            window_seconds=window_seconds,
            key_prefix=key_prefix,
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to initialize Redis rate limiter: {redis_url}") from exc
