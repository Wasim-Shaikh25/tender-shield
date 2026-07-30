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

## What to look for in Jaeger

After generating traffic:

1. Open http://localhost:16686/search?service=tendershield-backend
2. Select a trace to see request spans.
3. Look for:
   - `GET /api/health` and other route spans
   - Long-running database or external-API calls nested under request spans
   - Error spans (tagged `error=true`) when a 5xx or exception occurs

## Production notes

- Jaeger is a single-node all-in-one image; for production use a scalable backend such as Jaeger + Cassandra/Elasticsearch or a managed service.
- Use `TS_OTEL_EXPORTER_OTLP_HEADERS=api-key=<key>` for hosted OTLP endpoints such as Grafana Cloud or Honeycomb.
- Sampling: the current implementation samples every request. For high-traffic production, configure a sampler in `app/core/tracing.py` (e.g. `TraceIdRatioBased`).
