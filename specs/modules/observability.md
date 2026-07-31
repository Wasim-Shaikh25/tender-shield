# Observability — Spec

**Status:** implemented  
**Requirement refs:** Build Doc §11.1 (health), §12 (production readiness), audit `TS-108`;
`docs/TenderShield_Market_Strategy_2026.md` §G.2–G.3 (cost instrumentation)  
**Task refs:** TS-178, TS-180, TS-182, TS-223

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

## Cost instrumentation (TS-223)

Answers the question the product cannot price without: **what does one completed
tender review actually cost?** Implemented in `app/core/costmeter.py`.

- **Environment variables**
  - `TS_LLM_PRICE_TABLE` — JSON, `{"<model>": {"input": <minor units per 1M tokens>,
    "output": ..., "cached_input": ...}}`. Empty by default.
  - `TS_MAX_TOKENS_PER_REVIEW` — token ceiling per review (default `400000`; `0` disables).
- **Public interface**
  - `review_cost_scope(opportunity_id=…, rulepack_version=…)` — context manager that
    meters everything inside it as one review. Nesting attributes work to the inner
    scope rather than double-counting.
  - `record_llm_usage(...)`, `record_ocr_pages(n)`, `record_worker_seconds(s)`,
    `record_storage_bytes(n)` — cost drivers.
  - `current_scope()` — the review being metered, if any.
  - `MeteredClient` in `app/core/llm.py` wraps every OpenRouter client, so token usage is
    recorded at the single choke point. `openrouter_client(stage)` labels calls for
    per-stage attribution (`risk.classify`, `assistant.chat`, `analytics.plan`).
- **Metrics emitted**
  - Counters: `ts_llm_calls_total`, `ts_llm_prompt_tokens_total`,
    `ts_llm_completion_tokens_total`, `ts_llm_cached_tokens_total`,
    `ts_llm_cost_minor_total`, `ts_llm_unpriced_calls_total`, `ts_ocr_pages_total`,
    `ts_storage_bytes_total`, `ts_reviews_metered_total`, `ts_review_unpriced_total`,
    `ts_review_token_ceiling_exceeded_total`.
  - Histograms (p50/p95 come from these): `ts_review_cost_minor`,
    `ts_review_total_tokens`, `ts_review_wall_seconds`, `ts_worker_seconds`.

### Behavior

C1. Money is in **minor units**, integer arithmetic, one rounding at the end
    (`CLAUDE.md` §4). Prices are quoted per million tokens.
C2. **There is no built-in price table.** Rates differ per provider, contract and date.
    An unpriced model still has its tokens counted and is reported as unpriced —
    cost is never silently understated as zero.
C3. **Only fully-priced reviews feed `ts_review_cost_minor`.** A partially priced
    review would understate p50/p95, so it increments `ts_review_unpriced_total`
    instead.
C4. Cached tokens are treated as a subset of prompt tokens and billed at the cached rate.
C5. **Instrumentation never breaks a review.** A malformed usage object, a missing
    price, or an unparseable price table is logged and swallowed; the model response is
    returned unchanged.
C6. The **token ceiling guards the retrieval-first cost property** (Strategy Doc §G.3):
    cost must scale with pattern count, not document length. Exceeding it logs a warning
    naming the opportunity and increments a counter, so a change that starts sending whole
    documents to a model surfaces as a signal rather than a bill.
C7. Usage recorded outside any scope still reaches metrics; only per-review attribution
    requires a scope.

### Acceptance criteria

A9. Cost is integer minor units; output, input and cached tokens are priced separately.  
A10. An unpriced model yields `fully_priced == False` and a populated `unpriced_models`.  
A11. Nested scopes do not double-count; a scope closes even when its body raises.  
A12. `MeteredClient` records usage from a real-shaped response and passes non-metered
     attributes through untouched.  
A13. A response whose usage object raises is still returned to the caller.  
A14. Exceeding `TS_MAX_TOKENS_PER_REVIEW` logs a token-ceiling warning; `0` disables it.  
A15. A partially priced review is excluded from the cost histogram.

Covered by `backend/tests/test_costmeter.py` (21 tests).

## Data owned

None. Tracing and cost metering are ephemeral, runtime-only concerns exposed through
metrics and structured logs. No tables or files.

> Persisting per-review cost for long-horizon analysis is deliberately out of scope here:
> cost data is cross-cutting and `CLAUDE.md` §2 gives table ownership to modules, so it
> belongs to `analytics` if and when historical retention is needed. Prometheus histograms
> already answer the p50/p95 question for a running deployment.

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
