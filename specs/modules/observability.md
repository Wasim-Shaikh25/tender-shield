# Observability — Spec

**Status:** implemented  
**Requirement refs:** Build Doc §11.1 (health), §12 (production readiness), audit `TS-108`  
**Task refs:** TS-178

## Purpose

Provide production-ready visibility into the TenderShield backend: structured logs,
metrics, error tracking, and distributed tracing. Tracing is opt-in so local dev
remains lightweight, but the self-hosted Jaeger/Grafana stack and OTLP exporter
are fully wired so any deployment can turn it on.

## Public interface

- **Environment variables**
  - `TS_OTEL_ENABLED` — turn OpenTelemetry tracing on/off (default false).
  - `TS_OTEL_SERVICE_NAME` — service name reported to collectors (default `tendershield-backend`).
  - `TS_OTEL_EXPORTER_OTLP_ENDPOINT` — OTLP trace endpoint (default `http://localhost:4318/v1/traces`).
  - `TS_OTEL_EXPORTER_OTLP_HEADERS` — optional `key1=val1,key2=val2` headers for hosted OTLP.
- **Runtime behavior**
  - `init_tracing(app, settings)` instruments the FastAPI application and sets the
    global tracer provider when `TS_OTEL_ENABLED=true`.
  - Every HTTP request creates a span with the route and HTTP attributes.
  - Spans are exported asynchronously via `BatchSpanProcessor`.
- **Observability services**
  - Jaeger all-in-one: OTLP gRPC/HTTP collector + UI at `http://localhost:16686`.
  - Grafana: pre-provisioned Jaeger data source at `http://localhost:3100`.
- **Automation**
  - `scripts/verify-traces.sh` boots a temporary Jaeger, starts the backend with
    OTLP enabled, calls `/api/health`, and asserts a trace appears in Jaeger.

## Data owned

None. Tracing is an ephemeral, runtime-only concern. No tables or files.

## Behavior

B1. Tracing is disabled by default; the app boots and runs normally when
    `TS_OTEL_ENABLED=false` or when the OpenTelemetry packages are missing.
B2. When enabled, `init_tracing` configures a `TracerProvider` with a
    `BatchSpanProcessor` pointing at the configured OTLP endpoint.
B3. `FastAPIInstrumentor` wraps the application so every request becomes a span.
B4. The exporter uses OTLP/HTTP by default to avoid gRPC client complexity.
B5. The docker-compose `observability` profile starts Jaeger and Grafana with
    pre-provisioned data source configuration.
B6. `scripts/verify-traces.sh` is the acceptance test for the tracing pipeline.

## Acceptance criteria

A1. `TS_OTEL_ENABLED=true` does not break local dev boot or tests.  
A2. A request to `/api/health` produces a trace visible in Jaeger within 60 seconds.  
A3. `scripts/verify-traces.sh` exits 0 and prints the Jaeger search URL.  
A4. The docker-compose observability profile starts both Jaeger (16686) and Grafana (3100).

## Out of scope

- Metrics correlation inside spans (Phase 1+).
- Automatic instrumentation of SQLAlchemy/celery (can be added with extra OTEL instrumentors later).
- Production-scale Jaeger deployment (Cassandra/ES backend) — self-hosted all-in-one is the local/staging default.

## Assumptions

- OpenTelemetry libraries are installed as production dependencies; they are optional at runtime.
