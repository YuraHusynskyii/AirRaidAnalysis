"""Tests for load test SLO evaluation."""

from __future__ import annotations

import pytest

from src.load_test import LoadTestResult, evaluate_slo, run_load_test


def test_evaluate_slo_passes_when_within_targets() -> None:
    """SLO evaluation passes for low latency and zero errors."""
    result = LoadTestResult(
        total_requests=10,
        successful_requests=10,
        failed_requests=0,
        latencies_seconds=[0.05, 0.08, 0.1, 0.12, 0.15],
    )
    slo = evaluate_slo(
        result,
        p95_latency_max_seconds=0.5,
        max_error_rate=0.01,
    )
    assert slo.passed is True


def test_evaluate_slo_fails_on_high_latency() -> None:
    """SLO evaluation fails when p95 latency exceeds target."""
    result = LoadTestResult(
        total_requests=5,
        successful_requests=5,
        failed_requests=0,
        latencies_seconds=[0.6, 0.7, 0.8, 0.9, 1.0],
    )
    slo = evaluate_slo(
        result,
        p95_latency_max_seconds=0.5,
        max_error_rate=0.01,
    )
    assert slo.passed is False
    assert any("p95 latency" in message for message in slo.messages)


def test_run_load_test_requires_positive_requests() -> None:
    """Load test validates request count."""
    with pytest.raises(ValueError, match="total_requests must be positive"):
        run_load_test(
            base_url="http://localhost:8000",
            path="/health",
            total_requests=0,
        )
