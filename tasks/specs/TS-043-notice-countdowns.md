# TS-043 — Notice-deadline countdowns + alerts driven by the notice-rule register

**Status:** todo
**Requirement:** Doc §0.1 (P3), §10
**Spec(s) updated:** `specs/modules/baseline.md` (to be updated when built)
**Module(s):** `baseline`
**Severity / Gate:** P2 · Phase 1 MVP

## What this builds

Turns TS-041's static notice-rule register into a live countdown: alerts as
a post-award notice deadline (e.g. "notice of claim within 28 days of the
delay event") approaches, reusing the deadline-wall/digest pattern from
TS-015/TS-027.

## Implementation (reference plan — not yet built)

- Compute each `NoticeRule`'s trigger date from the relevant real-world
  event date (entered by the user post-award) plus its extracted period.
- Feed into `notifications.digest` (TS-027) the same way deadline-wall
  alerts do today.

## Files touched (planned)

- `backend/app/modules/baseline/{notices,service,router}.py`
- `backend/app/modules/notifications/digest.py` (consumer wiring)

## Tests (planned)

- `backend/tests/modules/baseline/test_notices.py::test_countdown`

## Acceptance criteria

- [ ] A notice rule with a trigger event date produces a countdown that
      surfaces in the same alerting channel as deadline-wall alerts.

## Commit

Not yet implemented.
