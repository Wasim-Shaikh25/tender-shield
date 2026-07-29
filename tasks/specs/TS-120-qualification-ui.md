# TS-120 — Bid qualification / eligibility UI

**Status:** todo
**Requirement:** [R-023](../../specs/requirements/R-023-unexposed-capabilities.md)
**Spec(s) updated:** `specs/modules/qualification.md` (to be updated when built)
**Module(s):** frontend, `qualification`
**Severity / Gate:** P1 · Gate 7

## What this builds

A frontend surface for TS-049's Qualification Compliance Matrix (already
built server-side, no UI): eligibility criteria (turnover, similar-project
experience, equipment) with met/not-met/unknown status and the citation
for each. Directly informs the bid/no-bid decision (TS-111) and should
surface alongside it.

## Implementation (reference plan — not yet built)

A qualification tab/panel on the opportunity page listing each criterion
from TS-049's `QualificationCriterion`, its status, and its source quote —
placed next to (or feeding directly into) TS-111's decision UI so a
reviewer sees exactly which gaps drove the recommendation.

## Files touched (planned)

- `frontend/app/opportunities/[id]/qualification/page.tsx` (new)

## Tests (planned)

- Manual verification against TS-049's existing backend data.

## Acceptance criteria (R-023)

- [ ] Every qualification criterion's status and source quote is visible
      in the UI, not just via direct API call.
- [ ] The qualification panel is visible alongside the bid/no-bid decision
      UI (TS-111).

## Commit

Not yet implemented.
