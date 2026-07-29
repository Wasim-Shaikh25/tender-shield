# TS-078 — Update tests and verify ruff/pytest/frontend build for tenant refactor

**Status:** done
**Requirement:** Doc §11.1
**Spec(s) updated:** none
**Module(s):** —
**Severity / Gate:** P1 · Phase 1 (remaining)

## What this builds

The verification pass closing out TS-074..077: every test touching the old
`org`/`org_id` shape updated to the new `Workspace`/`workspace_id` shape,
and a full green run across `ruff`, `pytest`, and the frontend build —
proving TS-074's A1 ("`pytest` passes after `org_id` is renamed") and A4
("existing pre-bid flow still works through workspace-scoped RLS").

## Implementation

Updated fixtures/factories across `backend/tests/` to construct
`Workspace`/`WorkspaceMember` instead of the removed `org`/`org_members`;
re-ran `ruff check .`, `pytest -q`, and `npm run build` to confirm the
refactor introduced no regression.

## Files touched

- `backend/tests/**` (fixture updates across modules)

## Tests

Full existing suite, updated in place — this task's deliverable is the
suite passing, not new tests.

## Acceptance criteria

- [x] `ruff check .` and `pytest -q` both pass post-refactor.
- [x] `npm run build` passes post-refactor.
- [x] The pre-bid flow (upload → classify → deadlines → risk → BOQ →
      review → export) still works end-to-end under the new tenant model.

## Commit

Predates commit-granular history (PR #10 bulk import).
