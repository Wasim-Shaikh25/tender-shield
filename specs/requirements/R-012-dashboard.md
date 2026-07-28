# R-012 — Portfolio dashboard

**Status:** draft
**Severity:** P1 — no cross-tender view; the `analytics` module has no consumer
**Requirement refs:** Doc §1.1, §9, §10
**Task refs:** TS-102
**Gap refs:** `docs/GAP_ANALYSIS.md` §4.4
**Specs to update:** `specs/frontend.md`, `specs/modules/analytics.md`

## Purpose

There is no dashboard. `/opportunities` (`app/opportunities/page.tsx`, 118 lines)
is a flat list with a create box, and the deadline wall exists **per opportunity
only** — so the one view that would make this a daily-use product, "what is due
across all my live bids", does not exist.

Meanwhile the `analytics` module (`backend/app/modules/analytics/`) is fully
implemented with a router, service and tests, and has **zero frontend consumers**.

The commercial argument: a tool opened once per tender is a tool that gets
forgotten between tenders. A tool that owns the deadline view is opened daily,
and daily-opened tools get renewed. This is the difference between the Pro plan
renewing and not.

## What the dashboard must answer

In priority order, because the layout should follow it:

1. **What is due soon, across every live opportunity?** — the cross-tender
   deadline wall. Missing a submission deadline is the failure the product
   exists to prevent, and today that view does not exist anywhere.
2. **What needs my attention?** — findings awaiting review, blocking export.
3. **Where is each bid?** — pipeline by status.
4. **What did we learn?** — severity mix, common risk categories.
5. **Where am I against my plan?** — usage vs quota (R-009).

## Backend

### B.1 One aggregate endpoint

Five separate calls on page load is five round trips and five loading states.
One endpoint, one shape:

```python
# backend/app/modules/analytics/router.py

@router.get("/dashboard")
def dashboard(
    request: Request,
    horizon_days: int = 30,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    """Portfolio summary for the caller's workspace (Doc §9).

    Aggregated server-side: the client must never pull every finding to count
    them, and severity ordering is deterministic code, never inferred.
    """
    return _service(request, session).dashboard(principal.workspace_id, horizon_days=horizon_days)
```

```json
{
  "deadlines": [
    {"opportunity_id": "…", "opportunity_title": "NHAI Package 4",
     "kind": "submission", "due_at": "2026-08-04T14:00:00Z", "days_left": 7,
     "confirmed": true, "source_page": 12, "urgency": "critical"}
  ],
  "attention": {
    "findings_pending_review": 23,
    "opportunities_blocked_from_export": 3,
    "unconfirmed_deadlines": 5,
    "documents_needing_ocr": 1
  },
  "pipeline": {"draft": 2, "in_review": 3, "submitted": 4, "won": 1, "lost": 2, "no_bid": 1},
  "risk_mix": {"critical": 4, "high": 18, "medium": 40, "low": 12, "info": 6},
  "top_categories": [{"category": "payment", "count": 12, "label": "Payment terms"}],
  "usage": {"plan": "pro", "reviews_used": 6, "reviews_included": 10,
            "seats_used": 4, "seats_included": 10, "period_end": "2026-08-28T00:00:00Z"},
  "activity": [{"at": "…", "actor_email": "…", "action": "finding.accepted",
                "opportunity_title": "…"}]
}
```

### B.2 Urgency is deterministic

```python
# backend/app/modules/analytics/service.py

def _urgency(days_left: int | None, confirmed: bool) -> str:
    """Deadline urgency is computed, never inferred (Doc §6.2 — date arithmetic
    is deterministic code). An unconfirmed deadline is escalated one level:
    an extracted-but-unverified date is more dangerous than a verified one,
    not less."""
    if days_left is None:
        return "unknown"
    base = ("critical" if days_left <= 2 else
            "high" if days_left <= 7 else
            "medium" if days_left <= 14 else "low")
    if not confirmed and base in ("medium", "low"):
        return {"medium": "high", "low": "medium"}[base]
    return base
```

### B.3 Cross-module data, no cross-module imports

`analytics` must reach ingestion (deadlines, opportunities), findings and review
through registry capabilities only:

```python
class AnalyticsService:
    def __init__(self, session, *, ingestion_factory=None, findings_factory=None,
                 review_factory=None, billing_entitlements=None):
        ...

    def dashboard(self, workspace_id, *, horizon_days=30) -> dict:
        if self._ingestion_factory is None:
            return self._empty("ingestion_unavailable")   # degrade, never crash
        ...
```

Each section degrades independently: with `billing` disabled the `usage` block is
`null` and the rest still renders (spec core B2).

### B.4 Query cost

`list_deadlines` is per-opportunity today (`ingestion/service.py:136`). Calling
it in a loop is N+1. Add a workspace-wide capability:

```python
def list_deadlines_for_workspace(self, workspace_id, *, before: datetime | None = None,
                                 statuses: tuple[str, ...] = ("draft", "in_review", "submitted")):
    """One query across the workspace, ordered by due date. Indexed on
    (workspace_id, due_at) — the dashboard is the most-loaded page in the app."""
```

Migration adds `ix_deadlines_workspace_due ON deadlines (workspace_id, due_at)`.

## Frontend

### B.5 Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Acme Infra ▾            Pro · 6/10 reviews          [+ New] │
├─────────────────────────────────────────────────────────────┤
│ ⚠ 2 submissions due this week                               │
├──────────────────────────────┬──────────────────────────────┤
│ DEADLINE WALL (30 days)      │ NEEDS ATTENTION              │
│ ● 2d  NHAI Pkg 4 · submission│ 23 findings pending review   │
│ ● 5d  MSRDC · pre-bid query  │ 3 packs blocked from export  │
│ ○ 12d Metro C3 · EMD         │ 5 unconfirmed deadlines      │
├──────────────────────────────┼──────────────────────────────┤
│ PIPELINE                     │ RISK MIX                     │
│ Draft 2 · Review 3 · Sub 4   │ ▇▇ 4 crit · 18 high · …      │
└──────────────────────────────┴──────────────────────────────┘
```

The deadline wall is the largest element and appears first. Everything else is
secondary.

### B.6 Deadline urgency, visually

Colour alone is insufficient — roughly 1 in 12 men have a colour-vision
deficiency, and this is a safety-critical view. Every urgency level carries
colour **and** an icon **and** text:

```tsx
const URGENCY = {
  critical: { dot: "bg-red-600",   icon: "🔴", label: "Due in 2 days or less" },
  high:     { dot: "bg-amber-500", icon: "🟠", label: "Due this week" },
  medium:   { dot: "bg-yellow-400",icon: "🟡", label: "Due in two weeks" },
  low:      { dot: "bg-slate-300", icon: "⚪", label: "Due later" },
  unknown:  { dot: "bg-slate-200", icon: "❔", label: "No date extracted" },
} as const;
```

Unconfirmed deadlines render with a dashed border and a "verify" affordance —
they are extracted facts awaiting human confirmation, and the tri-state labelling
invariant (`specs/000-product-overview.md` §Product invariants 5) applies here as
much as in the findings list.

### B.7 Routing

`/` currently renders marketing copy (`app/page.tsx`) for everyone. After this:

- signed out → marketing page
- signed in → redirect to `/dashboard`
- `/opportunities` remains the full list; the dashboard links into it

## Behavior

- **B1** One request populates the dashboard.
- **B2** Deadlines are aggregated across all live opportunities, ordered by due
  date, within a configurable horizon.
- **B3** Urgency is computed deterministically; unconfirmed deadlines escalate
  one level.
- **B4** Every section degrades independently when its module is disabled.
- **B5** Counts are aggregated in SQL, never by fetching rows to the client.
- **B6** Urgency is conveyed by colour, icon and text together.
- **B7** Closed opportunities (won/lost/no_bid) are excluded from the deadline
  wall but counted in the pipeline.
- **B8** Empty states are designed, not blank: a new workspace sees a first-run
  checklist.

## Acceptance criteria

- **A1** `GET /analytics/dashboard` returns all sections for a workspace with
  data, in one request.
- **A2** Deadlines from three different opportunities appear in one ordered list.
- **A3** A deadline 1 day out is `critical`; an unconfirmed one 10 days out is
  `high`, not `medium`.
- **A4** With `findings` disabled, `risk_mix` is `null` and the request still
  returns 200.
- **A5** A workspace with 500 opportunities loads the dashboard in < 500 ms p95
  (query count independent of opportunity count).
- **A6** Signing in redirects to `/dashboard`; signing out returns to `/`.
- **A7** A new workspace sees the first-run checklist, not empty panels.
- **A8** The dashboard shows only the current workspace's data after switching
  (R-011).
- **A9** Urgency levels are distinguishable in greyscale.

## Out of scope

- Cross-tender outcome graph / win-rate learning — Phase 3, and `/help` already
  labels it "planned".
- Custom dashboard layouts.
- Exportable dashboard reports.
- Team-activity feed beyond the last 10 audit entries.

## Assumptions

- `assumption:` 30-day default horizon. Configurable per user later if asked for.
- `assumption:` Opportunity status values are `draft|in_review|submitted|won|lost|no_bid`.
  Confirm against `ingestion/models.py` before implementing.
