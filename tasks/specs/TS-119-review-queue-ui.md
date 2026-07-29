# TS-119 — Review queue + audit viewer UI

**Status:** todo
**Requirement:** [R-023](../../specs/requirements/R-023-unexposed-capabilities.md)
**Spec(s) updated:** `specs/modules/review.md` (to be updated when built)
**Module(s):** frontend, `review`
**Severity / Gate:** P0 (release-blocking) · Gate 7

## What this builds

`ExportService._gate_ok` (TS-021) blocks export until every finding is
accepted or rejected — but the only way to do that today is clicking
through findings inline on a single opportunity's Risks tab: no queue, no
bulk action, no filtering, no cross-opportunity view. For an 800-page pack
producing dozens of findings, this is the difference between a usable and
an unusable workflow — and it sits directly on the paid path: a customer
who has paid ₹7,500 (TS-089) cannot export until they finish a review flow
that has no proper interface. The `reviewer` role gates exactly three
endpoints total — this and `baseline/freeze` (which *is* reachable via the
Handover tab) — so the workflow the role is actually named for is the one
it currently cannot perform.

## Implementation (reference plan — not yet built)

A queue listing pending findings across an opportunity with
filter-by-severity/category, keyboard-navigable accept/reject, bulk accept
for a filtered set, visible progress toward the export gate, and the
audit trail of decisions (TS-021's existing `AuditLog`, widened by TS-114)
visible alongside.

## Files touched (planned)

- `frontend/app/opportunities/[id]/review/page.tsx` (new)
- `backend/app/modules/review/{router,service}.py` (bulk-accept endpoint,
  filter query params)

## Tests (planned)

- E2E: filtered bulk-accept clears the export gate (Playwright, TS-104's
  planned stack)

## Acceptance criteria (R-023, TS-119 §Acceptance)

- [ ] A reviewer can filter findings by severity/category and bulk-accept
      a filtered set.
- [ ] Progress toward the export gate is visible without opening each
      finding individually.
- [ ] The decision audit trail is visible alongside the queue.

## Commit

Not yet implemented.
