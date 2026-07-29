# TS-117 — Processing-failure visibility + retry; metering correction for failed runs

**Status:** todo
**Requirement:** [R-022 §B](../../specs/requirements/R-022-team-lifecycle-and-run-recovery.md)
**Spec(s) updated:** `specs/modules/risk.md`, `specs/modules/billing.md`
  (to be updated when built)
**Module(s):** `risk`, `billing`, frontend
**Severity / Gate:** P1 · Gate 6

## What this builds

Review runs are synchronous today with **no persisted run record** — a
failed OCR pass or LLM call surfaces as an HTTP error and vanishes: no
status, no failure record, no retry, no support-visible cause. This
collides directly with TS-087's metering: `authorize_review` meters at
processing *start* precisely so a re-run after an addendum is free — but
that also means a run that fails for internal reasons has already consumed
the customer's free or paid review, with no automatic correction. On the
paygo plan that's ₹7,500 charged for nothing. It also collides with the
25-minute p95 NFR, which implies the async model TS-105 builds — and async
work with no visible state is unusable.

## Implementation (reference plan — not yet built)

Persisted run records: state (`queued|running|succeeded|failed`),
started/finished timestamps, error class and message, triggering user —
built on TS-105's `Job` model rather than a parallel record type. Progress
and failure state visible in the UI with a retry action. **Metering
correction**: a run that fails for an internal reason must not consume the
entitlement — either by not metering until success, or by writing a
compensating refund event (`assumption:` flagged as a product decision
still needing owner sign-off). Support can see the failure cause without
database access (ties into TS-125's planned ops console).

## Files touched (planned)

- `backend/app/modules/risk/{service,router}.py` (uses TS-105's `Job`)
- `backend/app/modules/billing/service.py` (compensating refund path)
- `frontend/app/opportunities/[id]/page.tsx` (failure/retry UI)
- Depends on TS-105 (job model)

## Tests (planned)

- `backend/tests/modules/risk/test_service.py::test_failed_run_does_not_consume_entitlement`
- `backend/tests/modules/billing/test_service.py::test_compensating_refund_on_internal_failure`

## Acceptance criteria (R-022 §B, B1–B5)

- [ ] A failed run is visible in the UI with a human-readable cause.
- [ ] Retrying does not double-meter or double-charge.
- [ ] A run failing for an internal reason leaves the entitlement
      unconsumed, or is visibly refunded.
- [ ] A user-input failure (corrupt file) is distinguishable from an
      internal failure.
- [ ] Run records are workspace-scoped and RLS-protected.

## Commit

Not yet implemented.
