# TS-087 — Enforce metering inside the review path via a `meter()` capability guard

**Status:** done
**Requirement:** [R-004 §A](../../specs/requirements/R-004-paywall-enforcement.md)
**Spec(s) updated:** `specs/modules/billing.md`, `specs/modules/risk.md`
**Module(s):** `core`, `risk`, `billing`
**Severity / Gate:** P0 · Gate 1

## What this builds

Closes a revenue leak: `billing.authorize_review` existed and was fully
implemented, but nothing called it. `POST /risk/opportunities/{id}/run` — the
endpoint that performs the work being sold — went straight to
`RiskService.run_opportunity` with no paywall check, and the frontend never
called `/billing/authorize-review` either. The paywall was an opt-in
courtesy nobody opted into.

## Current (the defect)

```python
# backend/app/modules/billing/module.py:6 (before this task)
def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    # Metering consumed by risk/ingestion before starting a review (Doc §7).
    reg.provide("billing.service_factory", lambda session: BillingService(...))
    # ^ the capability is published with a comment stating what should
    # consume it. Nothing does.
```

## Implementation

```python
# backend/app/core/deps.py
def meter(event: str):
    """Gate a billable action through the billing capability (Doc §7).
    Resolved by name so no module imports billing (CLAUDE.md §2). Billing
    disabled → unmetered + warning in dev, 503 in production (a disabled
    billing module must never silently become a free tier in production)."""
    def guard(request, session=Depends(get_session), principal=Depends(current_principal)):
        factory = request.app.state.ctx.registry.get("billing.service_factory")
        if factory is None:
            if request.app.state.ctx.settings.env == "production":
                raise HTTPException(503, "billing_unavailable")
            return None
        try:
            return factory(session).authorize_review(principal.workspace_id)
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code is None:
                raise
            raise HTTPException(402, detail={"code": code, "upsell": getattr(exc, "upsell", {})}) from exc
    return guard
```

```python
# backend/app/modules/risk/router.py
@router.post("/opportunities/{opportunity_id}/run")
def run(..., grant: Any = Depends(meter("review_started"))):   # 402 before any work
    ...
```

`authorize_review` gained an `opportunity_id` param so a re-run (e.g. after
an addendum) is free — only the *first* run of an opportunity is billable
(Doc §7 B1: "an addendum must never cost a second review, or customers stop
uploading addenda"). Race-safety: a `pg_advisory_xact_lock` per workspace
serializes concurrent metering so two simultaneous review-starts can't both
spend the single free review, backed by a `UNIQUE INDEX` on
`usage_events(workspace_id) WHERE event = 'free_review_used'` as a
belt-and-braces constraint. Emits `billing.paywall_hit`/
`billing.plan_activated`/`billing.payment_applied` events (previously
declared in the spec but never published).

## Files touched

- `backend/app/core/deps.py`
- `backend/app/modules/risk/router.py`
- `backend/app/modules/billing/{service,workspaces,module}.py`
- `backend/migrations/versions/` (unique index)

## Tests

- `backend/tests/modules/billing/test_service.py::test_authorize_review_race_safe`
- `backend/tests/modules/risk/test_router.py::test_run_requires_meter`

## Acceptance criteria (R-004 §A, A1–A5)

- [x] `POST /risk/.../run` returns 402 with an upsell payload when the free
      tier is exhausted, before any work runs.
- [x] Re-running an already-metered opportunity (e.g. after an addendum)
      does not consume a second review.
- [x] Two concurrent review-starts cannot both spend the single free
      review.

## Commit

Predates commit-granular history (PR #10 bulk import).
