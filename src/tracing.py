"""OpenTelemetry tracing helpers for serve and retrain workflows."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

_tracer = None
_tracing_enabled = False


def setup_tracing(
    *,
    enabled: bool,
    service_name: str,
    exporter_endpoint: Optional[str] = None,
) -> None:
    """Initialize OpenTelemetry tracer provider and optional OTLP exporter.

    Args:
        enabled: Whether tracing should be active.
        service_name: Logical service name attached to spans.
        exporter_endpoint: OTLP HTTP endpoint, e.g. ``http://localhost:4318/v1/traces``.

    Raises:
        RuntimeError: If tracer initialization fails while enabled.
    """
    global _tracer, _tracing_enabled

    if not enabled:
        _tracing_enabled = False
        _tracer = None
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        if exporter_endpoint:
            exporter = OTLPSpanExporter(endpoint=exporter_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name)
        _tracing_enabled = True
    except Exception as exc:
        raise RuntimeError("Failed to initialize OpenTelemetry tracing.") from exc


def is_tracing_enabled() -> bool:
    """Return whether tracing is active."""
    return _tracing_enabled


@contextmanager
def trace_span(
    name: str,
    attributes: Optional[dict[str, str]] = None,
) -> Iterator[None]:
    """Create an OpenTelemetry span or no-op when tracing is disabled.

    Args:
        name: Span name.
        attributes: Optional string attributes attached to the span.

    Yields:
        None
    """
    if _tracer is None:
        yield
        return

    with _tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield


def set_span_attributes(attributes: dict[str, str]) -> None:
    """Attach attributes to the current active span, if any."""
    if _tracer is None:
        return
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span is None:
            return
        for key, value in attributes.items():
            span.set_attribute(key, value)
    except Exception:
        return
