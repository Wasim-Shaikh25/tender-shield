# Observability — Spec

**Status:** implemented  
**Requirement refs:** Build Doc §11.1 (health), §12 (production readiness), audit `TS-108`  
**Task refs:** TS-178, TS-180, TS-182

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
  - `TS_ACCESS_LOG_ENABLED` — emit one access log line per request (default true).
  - `TS_LOG_REQUEST_BODIES` — optionally include redacted request/response body previews (default false).
  - `TS_LOG_FILE` — path for rotated JSON access logs (`logs/tendershield-access.log`).
  - `TS_APP_LOG_FILE` — path for rotated JSON application logs (`logs/tendershield-app.log`).
  - `TS_LOG_JSON` — write file logs as JSON (default true).
  - `TS_LOG_MAX_BYTES` / `TS_LOG_BACKUP_COUNT` — rotation settings.
- **Runtime behavior**
  - `init_tracing(app, settings)` instruments the FastAPI application and sets the
    global tracer provider when `TS_OTEL_ENABLED=true`.
  - Every HTTP request creates a span with the route and HTTP attributes.
  - `TracingAttributesMiddleware` enriches each span with `user.id`, `workspace.id`,
    `user.role`, and path parameters such as `ticket.id`.
  - `AccessLogMiddleware` writes one `tendershield.access` log line per request with
    method, path, status, duration, user, workspace, and request ID.
  - `configure_logging(settings)` sets up a stdout handler and rotated JSON file
    handlers for access logs and all application logs.
  - Spans are exported asynchronously via `BatchSpanProcessor`.
- **Observability services**
  - **Loki + Promtail**: logs are scraped from `/var/log/tendershield/*.log` and sent
    to Loki; Grafana provides the search UI at `http://localhost:3100`.
  - **Jaeger all-in-one**: OTLP gRPC/HTTP collector + UI at `http://localhost:16686`.
  - **Grafana**: pre-provisioned Loki and Jaeger data sources.
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
B4. `TracingAttributesMiddleware` runs inside the OTel span and copies principal and
    known path parameters to span attributes.
B5. `AccessLogMiddleware` logs every request/response with timing and principal info.
    Bodies are not logged unless `TS_LOG_REQUEST_BODIES=true`; when enabled, sensitive
    keys are redacted and previews are capped at 4 KB.
B5a. `configure_logging` writes access logs to a rotated JSON file with extra
    fields (`user_id`, `workspace_id`, `ticket_id` via path params, etc.).
B5b. Application logs are written to a separate rotated JSON file.
B6. The exporter uses OTLP/HTTP by default to avoid gRPC client complexity.
B7. The docker-compose `observability` profile starts Loki, Promtail, Jaeger,
    and Grafana with pre-provisioned data sources.
B8. `scripts/verify-traces.sh` is the acceptance test for the tracing pipeline.

## Acceptance criteria

A1. `TS_OTEL_ENABLED=true` does not break local dev boot or tests.  
A2. A request to `/api/health` produces a trace visible in Jaeger within 60 seconds.  
A3. `scripts/verify-traces.sh` exits 0 and prints the Jaeger search URL.  
A4. The docker-compose observability profile starts Loki (3101), Jaeger (16686),
    and Grafana (3100).  
A5. Access logs include `user=` and `workspace=` for authenticated requests.  
A6. A Jaeger trace for `GET /api/support/tickets/{ticket_id}` carries a `ticket.id` attribute.  
A7. A request to `/api/health` produces a line in `TS_LOG_FILE` with valid JSON.  
A8. Logs for a user/ticket can be found in Grafana/Loki using `{job="tendershield"} | json | user_id="..."`.

## Out of scope

- Metrics correlation inside spans (Phase 1+).
- Automatic instrumentation of SQLAlchemy/celery (can be added with extra OTEL instrumentors later).
- Production-scale Jaeger deployment (Cassandra/ES backend) — self-hosted all-in-one is the local/staging default.

## Assumptions

- OpenTelemetry libraries are installed as production dependencies; they are optional at runtime.
