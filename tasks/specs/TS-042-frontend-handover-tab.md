# TS-042 — Frontend: opportunity "Handover" tab

**Status:** done
**Requirement:** Doc §9, §0.1
**Spec(s) updated:** none
**Module(s):** frontend
**Severity / Gate:** P1 · Phase 1 MVP

## What this builds

The frontend surface for TS-041's `baseline` module: a "Handover" tab on the
opportunity detail page to freeze the baseline, view the notice register,
see the award-vs-tender delta, and download the handover pack.

## Implementation

Tab wired into `frontend/app/opportunities/[id]/` calling the `baseline`
module's `/api/baseline/*` routes (`freeze`, `notice_register`, `compare`,
`handover`) added in TS-041.

## Files touched

- `frontend/app/opportunities/[id]/` (Handover tab component)

## Tests

None yet — manual verification against the backend routes; frontend
component tests are not part of this task's scope.

## Acceptance criteria

- [x] A reviewer can freeze a baseline from the UI.
- [x] The notice register and award-vs-tender delta render from the
      backend's data, not hardcoded.

## Commit

Predates commit-granular history (PR #10 bulk import).
