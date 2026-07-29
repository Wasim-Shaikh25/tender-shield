# TS-102 — Portfolio dashboard: cross-tender deadline wall, attention, pipeline, usage

**Status:** todo
**Requirement:** [R-012](../../specs/requirements/R-012-dashboard.md)
**Spec(s) updated:** `specs/modules/analytics.md` (to be updated when built)
**Module(s):** `analytics`, `ingestion`, frontend
**Severity / Gate:** P1 · Gate 3

## What this builds

A single home-page dashboard answering "what needs my attention right now
across all my tenders" — today there is no cross-tender view; a user must
open each opportunity separately to see its deadlines/findings/status.

## Implementation (reference plan — not yet built)

```python
# backend/app/modules/analytics/router.py
@router.get("/dashboard")
def dashboard(request, horizon_days: int = 30, principal=Depends(require("viewer"))):
    """One aggregate endpoint — five separate calls on page load is five
    round trips and five loading states. Aggregated server-side; the
    client must never pull every finding to count them."""
    return _service(...).dashboard(principal.workspace_id, horizon_days=horizon_days)
```

Response shape: `deadlines[]` (cross-opportunity, urgency-tagged),
`attention` (findings pending review, opportunities blocked from export,
unconfirmed deadlines, documents needing OCR), `pipeline` (counts by
opportunity status), `risk_mix` (severity histogram), `top_categories`,
`usage` (plan/reviews/seats), `activity` (recent audit-log entries).

```python
def _urgency(days_left: int | None, confirmed: bool) -> str:
    """Deterministic, never inferred (CLAUDE.md §4). An UNCONFIRMED deadline
    is escalated one level — an extracted-but-unverified date is more
    dangerous than a verified one, not less."""
    base = ("critical" if days_left <= 2 else "high" if days_left <= 7 else
            "medium" if days_left <= 14 else "low")
    if not confirmed and base in ("medium", "low"):
        return {"medium": "high", "low": "medium"}[base]
    return base
```

`AnalyticsService` reaches `ingestion`/`findings`/`review`/`billing`
exclusively through registry capabilities (never imports another module,
CLAUDE.md §2) and each section degrades independently — e.g. with billing
disabled, `usage` is `null` and the rest still renders. Needs a new
workspace-wide `list_deadlines_for_workspace` capability (today's
`list_deadlines` is per-opportunity; calling it in a loop is N+1) backed by
a new index `ix_deadlines_workspace_due ON deadlines (workspace_id, due_at)`.

## Files touched (planned)

- `backend/app/modules/analytics/{router,service}.py`
- `backend/app/modules/ingestion/service.py` (`list_deadlines_for_workspace`)
- `backend/migrations/versions/` (new index)
- `frontend/app/dashboard/page.tsx`

## Tests (planned)

- `backend/tests/modules/analytics/test_dashboard.py` (each section's
  independent degradation when its source module is disabled)

## Acceptance criteria (R-012, A1–A9)

- [ ] The dashboard renders from one API call, not five.
- [ ] Deadline urgency is computed by fixed rule, and unconfirmed deadlines
      are escalated, never downgraded.
- [ ] Disabling `billing` nulls only the `usage` section; the rest of the
      dashboard still renders.

## Commit

Not yet implemented.
