# TS-105 — Async job pipeline: `Job` model, `JobQueue` protocol, inline + Celery backends, SSE progress

**Status:** todo
**Requirement:** [R-016 §A](../../specs/requirements/R-016-platform-scale.md)
**Spec(s) updated:** `specs/modules/core.md` (to be updated when built)
**Module(s):** `core`, `risk`, `ingestion`
**Severity / Gate:** P1 · Gate 4

## What this builds

Replaces the entire risk engine running synchronously inside the HTTP
request (the stated NFR is <25 min p95 for an 800-page pack — no load
balancer holds that connection) with a durable job model, a queue
abstraction with both an inline (dev/test) and Celery (production) backend,
and SSE progress streaming. Supersedes TS-034 (which was backlogged as
"needs Redis" — Redis was never actually the blocker; the missing piece was
the job model, status endpoint, and retry/idempotency design).

## Current (the problem)

```python
# backend/app/modules/risk/router.py:23 (current)
@router.post("/opportunities/{opportunity_id}/run")
def run(opportunity_id: str, ...):
    findings = _service(request, session).run_opportunity(...)   # runs inline, in-request
```

## Implementation (reference plan — not yet built)

```python
# backend/app/core/jobs.py — core, so any module can enqueue without importing another
class Job(Base, WorkspaceScopedMixin):
    """Durable record of background work, deliberately in the database rather
    than only in the broker: a customer asking "is my tender still
    processing?" must get an answer even if the broker restarted."""
    kind: Mapped[str]            # ingest_document | run_risk | run_boq | generate_artifact | export_pack
    status: Mapped[str]          # queued | running | succeeded | failed | cancelled
    progress: Mapped[int]        # 0..100
    idempotency_key: Mapped[str] # unique

class JobQueue(Protocol):
    def enqueue(self, kind: str, *, workspace_id, ref_id=None, payload: dict, idempotency_key: str) -> uuid.UUID: ...
    def cancel(self, job_id) -> bool: ...

class InlineQueue:
    """Runs handlers synchronously — dev/test default, keeps docker-compose
    Redis-free for local dev, every existing test keeps working."""

class CeleryQueue:
    """Production. Redis broker + result backend."""
```

```
POST /api/risk/opportunities/{id}/run     → 202 {job_id, status: "queued"}
GET  /api/jobs/{job_id}                   → {status, progress, stage, result, error_code}
GET  /api/jobs/{job_id}/events            → SSE stream of progress
POST /api/jobs/{job_id}/cancel            → 202
```

Rules: metering (TS-087) happens at *enqueue*, not execution, so the
paywall answers synchronously (immediate 402, not a job that fails 3
minutes later). Idempotency key is `(kind, ref_id, content_hash)` —
re-enqueueing identical work returns the existing job. Retries: 3 attempts,
exponential backoff, only for transient failures (never a validation
failure). Partial results persist per-pattern as they complete, so an 80%
failure leaves 80% of the value. Cancellation is cooperative. Per-workspace
concurrency caps prevent one tenant's 800-page pack from starving others.

## Files touched (planned)

- `backend/app/core/jobs.py` (new)
- `backend/app/modules/risk/router.py`, `backend/app/modules/ingestion/router.py`
- new `jobs` table + migration

## Tests (planned)

- `backend/tests/test_core_jobs.py` (idempotency, retry, partial results,
  cooperative cancellation — against `InlineQueue`)

## Acceptance criteria (R-016 §A, A1–A6)

- [ ] `POST /risk/.../run` returns 202 with a job id; the job completes
      asynchronously and its status is queryable.
- [ ] Re-enqueueing identical work (same idempotency key) returns the
      existing job, not a duplicate.
- [ ] Metering happens at enqueue — a paywalled request gets an immediate
      402, never a job that fails after starting.
- [ ] One workspace's large job does not block another workspace's job
      from starting.

## Commit

Not yet implemented.
