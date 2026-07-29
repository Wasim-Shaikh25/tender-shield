# TS-121 — Cross-tender comparison UI

**Status:** todo
**Requirement:** [R-023](../../specs/requirements/R-023-unexposed-capabilities.md)
**Spec(s) updated:** `specs/modules/comparison.md` (to be updated when built)
**Module(s):** frontend, `comparison`
**Severity / Gate:** P2 · Gate 7

## What this builds

A frontend surface for TS-050's Tender Comparison service (already built
server-side, no UI). Explicitly scoped to be built *with* TS-102's
portfolio dashboard rather than as a separate screen — they overlap enough
that a standalone comparison page would duplicate most of the dashboard's
layout and data.

## Implementation (reference plan — not yet built)

Fold TS-050's `ComparisonService` ranking output into TS-102's dashboard
build rather than shipping a separate route — a sortable table view of
opportunities ranked by risk/BOQ/deadline/readiness, reusing the
dashboard's existing data-fetch and layout.

## Files touched (planned)

- `frontend/app/dashboard/page.tsx` (extended, not a new route — see
  TS-102)

## Tests (planned)

- Manual verification against TS-050's existing backend data.

## Acceptance criteria (R-023)

- [ ] Cross-tender comparison is reachable from the dashboard, not a
      separate unlinked screen.

## Commit

Not yet implemented.
