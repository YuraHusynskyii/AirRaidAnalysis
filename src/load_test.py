"""Load testing utilities and SLO validation for inference API."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class LoadTestResult:
    """Aggregated load test statistics."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    latencies_seconds: list[float]

    @property
    def error_rate(self) -> float:
        """Return failed/total request ratio."""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests

    def percentile(self, pct: float) -> float:
        """Compute latency percentile from collected samples."""
        if not self.latencies_seconds:
            return 0.0
        ordered = sorted(self.latencies_seconds)
        index = int(round((pct / 100.0) * (len(ordered) - 1)))
        index = max(0, min(index, len(ordered) - 1))
        return ordered[index]


@dataclass(frozen=True)
class SloEvaluation:
    """SLO pass/fail outcome for one load test run."""

    passed: bool
    messages: list[str]
    p95_latency_seconds: float
    error_rate: float


def evaluate_slo(
    result: LoadTestResult,
    *,
    p95_latency_max_seconds: float,
    max_error_rate: float,
) -> SloEvaluation:
    """Evaluate load test result against latency and error-rate SLO targets.

    Args:
        result: Load test aggregate result.
        p95_latency_max_seconds: Maximum allowed p95 latency in seconds.
        max_error_rate: Maximum allowed error rate (0.0-1.0).

    Returns:
        SloEvaluation: Pass/fail summary with diagnostic messages.
    """
    p95 = result.percentile(95.0)
    messages: list[str] = []
    passed = True

    if p95 > p95_latency_max_seconds:
        passed = False
        messages.append(
            f"p95 latency {p95:.3f}s exceeds SLO {p95_latency_max_seconds:.3f}s"
        )
    if result.error_rate > max_error_rate:
        passed = False
        messages.append(
            f"error rate {result.error_rate:.3f} exceeds SLO {max_error_rate:.3f}"
        )
    if passed:
        messages.append("All SLO targets met.")

    return SloEvaluation(
        passed=passed,
        messages=messages,
        p95_latency_seconds=p95,
        error_rate=result.error_rate,
    )


def run_load_test(
    *,
    base_url: str,
    path: str,
    total_requests: int,
    payload: Optional[dict[str, Any]] = None,
    api_key: Optional[str] = None,
    timeout_seconds: int = 10,
) -> LoadTestResult:
    """Run a simple sequential load test against one HTTP endpoint.

    Args:
        base_url: Base URL, e.g. ``http://localhost:8000``.
        path: Request path, e.g. ``/health``.
        total_requests: Number of requests to send.
        payload: Optional JSON body for POST requests.
        api_key: Optional API key header value.
        timeout_seconds: Per-request timeout.

    Returns:
        LoadTestResult: Aggregate statistics.

    Raises:
        ValueError: If total_requests is not positive.
    """
    if total_requests <= 0:
        raise ValueError("total_requests must be positive.")

    url = f"{base_url.rstrip('/')}{path}"
    method = "POST" if payload is not None else "GET"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    latencies: list[float] = []
    success = 0
    failed = 0

    for _ in range(total_requests):
        request = Request(url, data=body, headers=headers, method=method)
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                if response.getcode() >= 400:
                    failed += 1
                else:
                    success += 1
        except (HTTPError, URLError, OSError, ValueError):
            failed += 1
        latencies.append(time.perf_counter() - started)

    return LoadTestResult(
        total_requests=total_requests,
        successful_requests=success,
        failed_requests=failed,
        latencies_seconds=latencies,
    )
