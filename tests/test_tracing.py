"""Tests for OpenTelemetry tracing helpers."""

from __future__ import annotations

from src.tracing import is_tracing_enabled, setup_tracing, trace_span


def test_trace_span_noop_when_tracing_disabled() -> None:
    """Disabled tracing should not raise during span context usage."""
    setup_tracing(enabled=False, service_name="test-service")
    assert is_tracing_enabled() is False

    with trace_span("unit.test"):
        assert True


def test_setup_tracing_can_enable_without_exporter_endpoint() -> None:
    """Tracing can initialize locally without OTLP exporter endpoint."""
    setup_tracing(
        enabled=True,
        service_name="test-service",
        exporter_endpoint=None,
    )
    assert is_tracing_enabled() is True

    with trace_span("unit.test.enabled"):
        assert True
