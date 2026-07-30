# Observability and tracing runbook

## Overview

TenderShield ships with three observability layers that can be used together:

1. **Structured logging and metrics** — JSON logs and Prometheus-style counters/gauges exposed at `/api/health/metrics`.
2. **Sentry** — error tracking and performance monitoring (opt-in via `TS_SENTRY_DSN`).
3. **OpenTelemetry + Jaeger + Grafana** — distributed tracing and trace search (opt-in via `TS_OTEL_ENABLED`).

## Self-hosted tracing stack (option 1)

The docker-compose file includes an `observability` profile that runs Jaeger and Grafana.

```bash
# Start the full stack including the observability services
docker compose --env-file .env.dev --profile observability up --build
```

UIs:

- Jaeger: http://localhost:16686
- Grafana: http://localhost:3100 (login `admin` / `admin`)

The Grafana data source is pre-provisioned to point at Jaeger.

## OpenTelemetry exporter (option 3)

Set these environment variables:

```bash
TS_OTEL_ENABLED=true
TS_OTEL_SERVICE_NAME=tendershield-backend
TS_OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318/v1/traces   # in docker
# or
TS_OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces # local
```

When `TS_OTEL_ENABLED` is true the backend instruments every HTTP request and exports spans to the OTLP endpoint. If the OTLP collector is unavailable, spans are dropped silently (the app still works).

## Verifying traces automatically

Run the included script:

```bash
./scripts/verify-traces.sh
```

This script starts a temporary Jaeger container, boots the backend with OTLP enabled, calls `/api/health`, and polls Jaeger until the trace appears. It prints the Jaeger search URL on success.

## Request access logs

Every request is logged to the `tendershield.access` logger:

```
GET /api/support/tickets/abc 200 12.5ms user=<uuid> workspace=<uuid> role=admin request_id=...
```

Set `TS_ACCESS_LOG_ENABLED=false` to disable. To log request/response body previews
(for short-term debugging), set `TS_LOG_REQUEST_BODIES=true`; sensitive keys are
redacted and previews are capped at 4 KB.

## Tracing a particular user or ticket

When OTel is enabled, spans are enriched with principal and path parameter attributes:

- `user.id` — authenticated user UUID
- `workspace.id` — current workspace UUID
- `user.role` — e.g. `owner`, `admin`, `viewer`
- `ticket.id` — from `/api/support/tickets/{ticket_id}`
- `opportunity.id` — from `/api/opportunities/{opportunity_id}`
- `http.request_id` — propagated/correlation ID

In Jaeger:

1. Open http://localhost:16686/search?service=tendershield-backend
2. Use the **Tags** box to filter, e.g. `user.id=<uuid>` or `ticket.id=<ticket-uuid>`.
3. Select a trace to see the route span and any nested database/external-call spans.
4. Error spans are tagged `error=true`; 5xx responses and exceptions are captured
   automatically by the FastAPI instrumentor.

## Production notes

- Jaeger is a single-node all-in-one image; for production use a scalable backend such as Jaeger + Cassandra/Elasticsearch or a managed service.
- Use `TS_OTEL_EXPORTER_OTLP_HEADERS=api-key=<key>` for hosted OTLP endpoints such as Grafana Cloud or Honeycomb.
- Sampling: the current implementation samples every request. For high-traffic production, configure a sampler in `app/core/tracing.py` (e.g. `TraceIdRatioBased`).
