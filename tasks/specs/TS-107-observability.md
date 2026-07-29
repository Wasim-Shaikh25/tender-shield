# TS-107 — Observability: structured logs, request ids, metrics, readiness probe, LLM cost controls

**Status:** todo
**Requirement:** [R-016 §C](../../specs/requirements/R-016-platform-scale.md)
**Spec(s) updated:** `specs/modules/core.md`, `specs/modules/health.md`
  (to be updated when built)
**Module(s):** `core`, `health`
**Severity / Gate:** P2 · Gate 4

## What this builds

Closes an operational blind spot: bare `logging` with no request ids or
correlation, no metrics, no tracing; `/api/health` reports loaded modules
but never checks the database, so a Postgres outage still returns healthy
and an orchestrator keeps routing traffic to a broken instance. Also: zero
LLM cost controls — `ANTHROPIC_API_KEY` enables the risk classifier and
assistant with no budget, no per-workspace cap, no caching, no circuit
breaker.

## Implementation (reference plan — not yet built)

```python
# backend/app/core/logging.py
def configure_logging(settings: Settings) -> None:
    """JSON logs in deployed environments, human-readable locally. Every
    record carries request_id, workspace_id, user_id from contextvars — a
    support question becomes one query, not a grep."""
```

Never logs: tender document text, JWTs, refresh/reset tokens, presigned
URLs, webhook bodies containing payment instruments — redacted by key name
at the formatter, not at each call site.

```
GET /api/health        → liveness: process is up, no dependency checks
GET /api/health/ready  → readiness: DB reachable, migrations current,
                          storage reachable, queue reachable
```

The split matters: a readiness failure should stop traffic; a liveness
failure should restart the process. Conflating them causes restart loops
during a database blip.

Prometheus metrics (request rate/latency/errors by route; job duration and
failure rate by kind; LLM tokens/cost by workspace; paywall hits by code);
Sentry-equivalent for exceptions with PII scrubbing on.

LLM cost controls: per-workspace monthly token budget (exceeded → fall
back to deterministic paths with a clear UI state, never a silent quality
drop); cache classifier results by `(pattern_id, clause_hash, model,
pack_version)` so re-running risk on an unchanged pack costs nothing;
circuit breaker on repeated provider failures; model pinned by
configuration, never floating.

Ops gaps closed in the same pass: backup/restore runbook with stated
RPO/RTO; staging environment (CI currently only builds/tests, nothing
deploys); secret scanning + dependency audit (`pip-audit`, `npm audit`) +
SAST in CI; moving `app/modules/_broken/` (a deliberate loader-resilience
test fixture) out of production source into `tests/fixtures/`.

## Files touched (planned)

- `backend/app/core/{logging,metrics}.py` (new)
- `backend/app/modules/health/router.py` (`/ready` endpoint)
- `.github/workflows/ci.yml` (secret scanning, dependency audit, SAST)
- `backend/app/modules/_broken/` → `backend/tests/fixtures/_broken/`

## Tests (planned)

- `backend/tests/modules/health/test_ready.py::test_ready_fails_on_db_down`
- `backend/tests/test_core_logging.py::test_never_logs_secrets`

## Acceptance criteria (R-016 §C, A10–A13)

- [ ] A database outage flips `/api/health/ready` unhealthy without
      restarting the process (`/api/health` liveness stays green).
- [ ] No log line ever contains a JWT, refresh token, or tender document
      text.
- [ ] A workspace exceeding its LLM token budget falls back to
      deterministic-only findings with a visible UI state, not a silent
      quality drop.

## Commit

Not yet implemented.
