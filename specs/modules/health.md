# Health — Spec

**Status:** implemented  
**Requirement refs:** Doc §11.1, `PRODUCTION_READINESS_AUDIT.md` F23 / O02  
**Task refs:** TS-031, TS-083, TS-108

## Purpose

A lightweight, Kubernetes-friendly health surface plus Prometheus-compatible metrics
and optional Sentry error tracking. The public surface is intentionally minimal to
avoid information disclosure; the detailed capability, dependency, and metrics
reports are gated behind super-admin authentication.

## Public interface

- **Capabilities published:** none.
- **Capabilities consumed (soft):** `auth.current_principal` (for `/details`).
- **Events emitted:** none.
- **Events consumed:** none.
- **API routes** (prefix `/api/health`):
  - `GET /` (unauthenticated, public) — `status`, `version`.
  - `GET /live` (unauthenticated, public) — liveness; returns 200 as long as the
    process can respond.
  - `GET /ready` (unauthenticated, public) — readiness probe checking DB, Redis,
    storage, and the Celery broker. Returns 503 if any critical dependency is
    unreachable.
  - `GET /metrics` (unauthenticated, public) — Prometheus exposition text with
    per-process `http_requests_total`, `http_5xx_total`, `http_4xx_total`, and
    `http_request_duration_seconds`.
  - `GET /details` (super-admin) — loaded modules, failed modules, missing soft
    dependencies, capability names, and dependency statuses.

## Data owned

None. Responses are constructed from `app.state.load_report`, `app.state.ctx.registry`,
and the in-memory `_Metrics` collector.

## Behavior

- **B1 — Public health:** `GET /api/health` returns `{"status":"ok","version":"0.1.0"}`
  and never queries the database, so it remains available during DB outages.
- **B2 — Liveness:** `GET /api/health/live` returns 200 immediately; it proves the
  process can accept HTTP and is used by orchestrators to decide whether to restart
  a pod.
- **B3 — Readiness:** `GET /api/health/ready` checks every configured dependency and
  returns either 200 (`"status": "ok"`) or 503 (`"status": "degraded"`) with a
  per-dependency status map. Unconfigured non-critical dependencies report
  `"skipped"`.
- **B4 — Metrics:** `GET /api/health/metrics` serves Prometheus text built from an
  in-process collector updated by `MetricsMiddleware`. It does not depend on any
  external time-series database.
- **B5 — Detailed report:** `GET /api/health/details` requires an authenticated
  super-admin. It returns the module load report, capability list, and the same
  dependency status map as `/ready`.
- **B6 — Sentry:** Sentry is initialized at startup if `TS_SENTRY_DSN` is set and
  `sentry-sdk` is installed. When the DSN or package is absent, the feature
  degrades silently.
- **B7 — Safe to call:** The public endpoints require no DB query; `/details` is
  the only endpoint that opens a session and only when an admin token is supplied.

## Acceptance criteria

- A1: `GET /api/health` returns `status: ok` and `version` without authentication.
- A2: `GET /api/health/live` returns 200 and no body is required for orchestrator
  liveness probes.
- A3: `GET /api/health/ready` checks DB connectivity, Redis (when configured),
  storage, and Celery broker. With all dependencies healthy it returns 200 and
  `status: ok`.
- A4: `GET /api/health/ready` returns 503 with `status: degraded` if the database
  is unreachable.
- A5: `GET /api/health/metrics` returns Prometheus exposition text containing
  `http_requests_total` and `http_request_duration_seconds`.
- A6: `GET /api/health/details` without a super-admin token returns 403.
- A7: `GET /api/health/details` with a super-admin token returns loaded modules,
  capabilities, and dependency statuses.

## Out of scope

- Distributed trace propagation (P2).
- Alert-manager rules for 5xx rate / webhook signature failures / Celery queue depth
  (P2 — documented in `docs/deployment.md`).
