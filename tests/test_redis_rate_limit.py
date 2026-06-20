"""Tests for Redis-backed shared rate limiter."""

from __future__ import annotations

from collections import defaultdict

import pytest

from src.redis_rate_limit import RedisSlidingWindowRateLimiter


class FakeRedisSortedSet:
    """Minimal in-memory Redis sorted-set emulation for unit tests."""

    def __init__(self) -> None:
        self._sets: dict[str, dict[str, float]] = defaultdict(dict)
        self._ttl: dict[str, int] = {}

    def zremrangebyscore(self, name: str, minimum: float, maximum: float) -> int:
        members = self._sets[name]
        to_delete = [member for member, score in members.items() if minimum <= score <= maximum]
        for member in to_delete:
            del members[member]
        return len(to_delete)

    def zcard(self, name: str) -> int:
        return len(self._sets[name])

    def zrange(
        self,
        name: str,
        start: int,
        end: int,
        *,
        withscores: bool = False,
    ) -> list:
        items = sorted(self._sets[name].items(), key=lambda item: item[1])
        sliced = items[start : end + 1]
        if not withscores:
            return [member for member, _score in sliced]
        flattened: list = []
        for member, score in sliced:
            flattened.extend([member, score])
        return flattened

    def zadd(self, name: str, mapping: dict[str, float]) -> int:
        self._sets[name].update(mapping)
        return len(mapping)

    def expire(self, name: str, seconds: int) -> bool:
        self._ttl[name] = seconds
        return True


def test_redis_rate_limiter_blocks_after_limit() -> None:
    """Redis limiter denies requests once shared window capacity is reached."""
    fake = FakeRedisSortedSet()
    limiter = RedisSlidingWindowRateLimiter(
        client=fake,
        max_requests=2,
        window_seconds=60.0,
        key_prefix="test",
    )

    first = limiter.check("client-a")
    second = limiter.check("client-a")
    third = limiter.check("client-a")

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.remaining == 0


def test_create_rate_limiter_requires_redis_url_for_redis_backend() -> None:
    """Factory validates redis_url when backend is redis."""
    from src.rate_limit import create_rate_limiter

    with pytest.raises(ValueError, match="redis_url is required"):
        create_rate_limiter(
            backend="redis",
            max_requests=10,
            window_seconds=60.0,
            redis_url=None,
        )
