# R-016 — Platform: async pipeline, object storage, observability, product metrics

**Status:** draft
**Severity:** P1 (async, storage) / P2 (observability) / P1 (metrics)
**Requirement refs:** Doc §1.3, §3.1, §3.3, §11.1, §11.2, §19
**Task refs:** TS-105 (async), TS-106 (storage), TS-107 (observability), TS-108 (metrics)
**Task files:** code-level detail (current-vs-target snippets, file:line, files touched, tests) now lives per-task, split out by TS-126's restructure: [TS-105](../../tasks/specs/TS-105-async-job-pipeline.md), [TS-106](../../tasks/specs/TS-106-s3-storage-adapter.md), [TS-107](../../tasks/specs/TS-107-observability.md), [TS-108](../../tasks/specs/TS-108-product-metrics.md), [TS-109](../../tasks/specs/TS-109-legal-commercial-surface.md). This document stays the business/behavior-level record (purpose, target behavior, acceptance criteria).

**Gap refs:** `docs/GAP_ANALYSIS.md` §5.1, §5.2, §5.3, §6.1
**Specs to update:** `specs/modules/ingestion.md`, `specs/modules/analytics.md`, `docs/deployment.md`

## Purpose

Four platform gaps that block scale and, in the case of §D, block the company
from knowing whether the product works.

---

## A. Async processing pipeline (TS-105)

### A.1 The problem

```python
# backend/app/modules/risk/router.py:23
@router.post("/opportunities/{opportunity_id}/run")
def run(opportunity_id: str, ...):
    findings = _service(request, session).run_opportunity(principal.workspace_id, opportunity_id)
```

The entire risk engine runs inside the HTTP request. The stated NFR is
**< 25 min p95 for an 800-page pack** (`specs/000-product-overview.md`
§Non-functional). No load balancer or browser holds that connection — and the
same document promises "stream results" and "processing continues offline",
neither of which is possible in this shape.

TS-034 is backlogged as "needs Redis", but Redis is not the blocker. There is no
job model, no status endpoint, no progress protocol, and no retry/idempotency
design. Those are design decisions, and they can be made now.

### A.2 Job model

```python
# backend/app/core/jobs.py — core, so any module can enqueue without importing another

class Job(Base, WorkspaceScopedMixin):
    """Durable record of background work. Deliberately in the database rather
    than only in the broker: a customer asking "is my tender still processing?"
    must get an answer even if the broker has been restarted (R-016 §A.2)."""

    _tablename_ = "jobs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    # ingest_document | run_risk | run_boq | generate_artifact | export_pack
    ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    # queued | running | succeeded | failed | cancelled
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)      # 0..100
    stage: Mapped[str | None] = mapped_column(String, nullable=True)               # human label
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### A.3 Queue abstraction

Do not couple modules to Celery. One protocol, two implementations — the
in-process one keeps tests synchronous and keeps `docker-compose` free of Redis
for local development.

```python
class JobQueue(Protocol):
    def enqueue(self, kind: str, *, workspace_id, ref_id=None,
                payload: dict, idempotency_key: str) -> uuid.UUID: ...
    def cancel(self, job_id) -> bool: ...


class InlineQueue:
    """Runs handlers synchronously. Dev/test default: every existing test keeps
    working, and the API shape is identical to the async path."""


class CeleryQueue:
    """Production. Redis broker + result backend."""
```

### A.4 API shape

```
POST /api/risk/opportunities/{id}/run     → 202 {job_id, status: "queued"}
GET  /api/jobs/{job_id}                   → {status, progress, stage, result, error_code}
GET  /api/jobs/{job_id}/events            → SSE stream of progress
POST /api/jobs/{job_id}/cancel            → 202
```

Metering (R-004) happens at **enqueue**, not at execution — the paywall must
answer synchronously so the user gets an immediate 402 rather than a job that
fails three minutes later.

### A.5 Rules

- **Idempotency**: `(kind, ref_id, content_hash)` — re-enqueueing the same work
  returns the existing job.
- **Retries**: 3 attempts, exponential backoff, only for transient failures
  (network, provider 5xx). Never retry a validation failure.
- **Partial results**: findings are persisted per pattern as they complete, so a
  failure at 80% leaves 80% of the value.
- **Cancellation** is cooperative — handlers check a flag between stages.
- **Timeouts**: hard cap per job kind; a hung OCR job must not occupy a worker
  forever.
- **Workspace fairness**: one workspace's 800-page pack must not starve every
  other tenant. Separate queues by expected duration, or cap concurrent jobs per
  workspace.

---

## B. Object storage (TS-106)

### B.1 The problem

```python
# backend/app/modules/ingestion/storage.py:1
"""File storage abstraction. LocalStorage writes to a per-org directory and is
the dev/test backend; an S3 backend (SSE-KMS, per-org prefix, Doc §11.2) is the
production adapter behind the same interface."""
```

The docstring describes an S3 adapter that does not exist. Only `LocalStorage`
is implemented. Consequences: horizontal scaling breaks (each replica sees only
its own uploads), the `docker-compose` deployment loses documents on container
replacement, and there is no encryption at rest, no lifecycle policy and no
ap-south-1 residency guarantee — the last being an explicit NFR.

### B.2 Target

```python
# backend/app/modules/ingestion/storage_s3.py

class S3Storage:
    """S3-compatible storage (AWS S3, MinIO). Per-workspace key prefix,
    SSE-KMS at rest, presigned URLs for direct download (Doc §11.2)."""

    def put(self, workspace_id: str, filename: str, data: bytes) -> tuple[str, str]:
        sha = hashlib.sha256(data).hexdigest()
        key = f"{workspace_id}/{sha}{Path(filename).suffix}"
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=data,
            ServerSideEncryption="aws:kms", SSEKMSKeyId=self._kms_key_id,
            Metadata={"workspace_id": str(workspace_id), "original_name": filename},
        )
        return key, sha

    def presigned_get(self, key: str, *, expires_in: int = 300) -> str:
        """Short-lived download URL. The key embeds the workspace id, but the
        URL itself is a bearer credential — 5 minutes, never logged."""
```

The `Storage` protocol needs `get`, `delete` and `presigned_get` added; today it
declares only `put` (`storage.py:12`), which is why nothing can re-read an
uploaded document.

Streaming matters here too: `put` takes `bytes`, which conflicts with R-003 §B.1
streaming uploads. Change the protocol to accept a file-like object and use
multipart upload for large objects.

### B.3 Ops requirements

- Bucket in **ap-south-1** (Mumbai) — data residency NFR.
- Versioning on; lifecycle to Glacier after 180 days; deletion after the
  retention period (needs a retention policy decision — none exists today).
- Block all public access; bucket policy scoped to the app role.
- Presigned URLs ≤ 5 minutes, never written to logs.
- MinIO in `docker-compose` so local development exercises the same code path.

---

## C. Observability (TS-107)

### C.1 Current

Bare `logging` with no request ids, no correlation, no metrics, no tracing, no
error reporting. `/api/health` reports loaded modules but **does not check the
database** — a Postgres outage still returns healthy, so an orchestrator will
happily keep routing traffic to a broken instance.

### C.2 Structured logging

```python
# backend/app/core/logging.py

def configure_logging(settings: Settings) -> None:
    """JSON logs in deployed environments, human-readable locally.

    Every record carries request_id, workspace_id and user_id from contextvars
    so a support question ("what happened to this customer's upload?") is one
    query, not a grep (R-016 §C.2).
    """
```

Middleware assigns a request id (honouring an inbound `X-Request-ID`), binds it
plus workspace/user to contextvars, logs one structured line per request with
method, path, status and duration, and returns the id in the response header.

**Never log**: tender document text (customer confidential), JWTs, refresh
tokens, reset tokens, presigned URLs, webhook bodies containing payment
instruments. Redact by key name at the formatter, not at each call site.

### C.3 Health

```
GET /api/health        → liveness: process is up (no dependency checks)
GET /api/health/ready  → readiness: DB reachable, migrations current, storage
                          reachable, queue reachable
```

The split matters: a readiness failure should stop traffic, a liveness failure
should restart the process. Conflating them causes restart loops during a
database blip.

### C.4 Metrics and errors

Prometheus metrics: request rate/latency/errors by route; job duration and
failure rate by kind; LLM tokens and cost by workspace; paywall hits by code;
webhook processing outcomes. Sentry (or equivalent) for exceptions, with PII
scrubbing on.

### C.5 LLM cost controls

None exist. `ANTHROPIC_API_KEY` enables the risk classifier and assistant with no
budget, no per-workspace cap, no caching and no circuit breaker.

- Per-workspace monthly token budget; exceeded → deterministic paths only, with
  a clear UI state rather than a silent quality drop.
- Cache classifier results by `(pattern_id, clause_hash, model, pack_version)` —
  re-running risk on an unchanged pack should cost nothing.
- Circuit breaker: on repeated provider failures, fall back to deterministic
  paths and surface the degradation.
- Model pinned by configuration, never floating.

### C.6 Ops gaps to close

- Backup/restore runbook with stated RPO/RTO (99.5% availability NFR, no runbook
  today).
- Staging environment; CI currently builds and tests but nothing deploys.
- Secret scanning, dependency audit (`pip-audit`, `npm audit`) and SAST in CI.
- Move `app/modules/_broken/` — a deliberate loader-resilience fixture — out of
  production source into `tests/fixtures/`.

---

## D. Product metrics (TS-108) — the highest-leverage item here

### D.1 Why this is not just telemetry

`specs/000-product-overview.md` §Phase gates defines the Phase-1 exit as deadline
**F1 ≥ 0.95**, QS acceptance **≥ 70%**, 10 real tenders, 3 paid conversions — and
a kill gate at "finding acceptance <50% after two eval cycles".

**None of these are measurable today.** The review module already records every
accept/reject decision in its audit log (`review/service.py:36`), so the raw
data exists; nothing aggregates it. The company therefore cannot tell whether
its own kill gate has been crossed.

Everything else in this document makes the product better. This tells the
business whether the product works.

### D.2 Acceptance-rate metric

```python
# backend/app/modules/analytics/service.py

def finding_acceptance(self, *, workspace_id=None, since=None, pack_version=None) -> dict:
    """Finding acceptance rate — the Phase-1 kill-gate metric (Doc §10).

    Denominator is REVIEWED findings, not all findings: unreviewed ones are
    pending, not rejected, and counting them would understate quality and could
    trip the kill gate on a product that is actually working.
    """
    return {
        "reviewed": ..., "accepted": ..., "edited": ..., "rejected": ...,
        "acceptance_rate": (accepted + edited) / reviewed if reviewed else None,
        "by_category": {...},          # which rule-packs earn their place
        "by_severity": {...},
        "by_pattern_id": {...},        # which individual patterns to retire
    }
```

`by_pattern_id` is the actionable cut: it identifies exactly which rule-pack
patterns to promote to `confidence: validated` and which to retire — the
governance loop `specs/modules/rulepacks.md` describes but has no data for.

### D.3 Deadline F1

Requires ground truth. `evals/in-works/` holds one synthetic tender with an
answer key. Needed: a golden set of real tenders with QS-verified deadlines, and
a scorer wired into CI:

```
evals/golden/<tender-id>/
    source/          # the pack (gitignored if licensing prevents committing)
    expected.yaml    # deadlines, key findings, BOQ defects — QS-verified
    provenance.md    # where it came from, who verified it, when
```

```python
def score_deadlines(expected: list[Deadline], actual: list[Deadline]) -> dict:
    """Precision/recall/F1 with a ±1 day tolerance on due_at and a matching
    `kind`. Deterministic — this is a measurement, not a judgement."""
```

`scripts/phase0_accuracy_test.py` exists as a standalone script; it needs to
become a CI job that fails when F1 regresses below the gate on the golden set.

### D.4 Funnel instrumentation

Events the business needs, none of which are emitted today: `signup`,
`email_verified`, `first_opportunity`, `first_upload`, `first_review_run`,
`first_finding_accepted`, `first_export`, `paywall_hit`, `checkout_started`,
`payment_succeeded`, `second_tender_uploaded`.

`second_tender_uploaded` is the important one — the kill gate is
"<40% second-tender conversion", and that is the metric that says whether the
product is habit-forming or a one-off curiosity.

### D.5 Privacy

Product analytics must be **event counts and identifiers, never tender content**.
No document text, no clause text, no quotes, no customer names in any analytics
store. The build doc's "no training on customer data" commitment extends to
telemetry.

---

## Acceptance criteria

**Async (A):**
- **A1** `POST /risk/.../run` returns `202` with a job id; the job completes
  asynchronously.
- **A2** `GET /jobs/{id}` reports progress ≥ 0 and a stage label while running.
- **A3** Re-enqueueing identical work returns the same job id.
- **A4** A worker killed mid-job leaves the job `running`, and a reaper marks it
  `failed` after the timeout with partial results retained.
- **A5** Metering returns 402 at enqueue time, not after processing.
- **A6** With `InlineQueue`, the existing test suite passes unchanged.

**Storage (B):**
- **A7** With `TS_STORAGE_BACKEND=s3`, uploads land in S3 under the workspace
  prefix with SSE-KMS.
- **A8** Two API replicas can read each other's uploads.
- **A9** Presigned URLs expire in 5 minutes and appear in no log.

**Observability (C):**
- **A10** Every log line carries `request_id`; the id is returned in the
  response header.
- **A11** No tender text, token or presigned URL appears in logs (assertion test
  over a redaction fixture).
- **A12** `/api/health/ready` returns 503 when the database is unreachable while
  `/api/health` still returns 200.
- **A13** A workspace over its LLM budget falls back to deterministic paths with
  a visible UI state.

**Metrics (D):**
- **A14** `GET /analytics/quality` returns acceptance rate overall, by category,
  by severity and by pattern id.
- **A15** The denominator excludes unreviewed findings.
- **A16** The golden-set scorer produces precision/recall/F1 and fails CI below
  the configured gate.
- **A17** Funnel events are emitted for every step in §D.4.
- **A18** No analytics payload contains document text (assertion test).

## Out of scope

- Multi-region deployment.
- Data warehouse / BI stack — the endpoints here are the source.
- Autoscaling policy.

## Assumptions

- `assumption:` Celery + Redis, per TS-034. The `JobQueue` protocol makes an
  alternative (RQ, Arq, SQS) a new adapter rather than a rewrite.
- `assumption:` Self-hosted Prometheus/Grafana. A managed APM would replace §C.4
  without changing the instrumentation.
- `assumption:` The golden set needs 5–10 real tenders with QS-verified answers.
  Acquiring them is a business task, not an engineering one, and it is the
  genuine critical path for the Phase-1 gate.
