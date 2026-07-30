"""OpenTelemetry tracing bootstrap.

Tracing is opt-in via TS_OTEL_ENABLED. When enabled, FastAPI requests are
instrumented and spans are exported via OTLP (HTTP). The default local target
is Jaeger's OTLP endpoint at http://localhost:4318/v1/traces.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from app.core.config import Settings

logger = logging.getLogger(__name__)


def _parse_headers(raw: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        headers[key.strip()] = value.strip()
    return headers


def init_tracing(app: FastAPI, settings: Settings) -> None:
    """Instrument the FastAPI app with OpenTelemetry if enabled."""
    if not settings.otel_enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.warning("OpenTelemetry packages not installed; skipping tracing: %s", exc)
        return

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_endpoint,
        headers=_parse_headers(settings.otel_exporter_otlp_headers),
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    logger.info("OpenTelemetry tracing enabled for service %r", settings.otel_service_name)
