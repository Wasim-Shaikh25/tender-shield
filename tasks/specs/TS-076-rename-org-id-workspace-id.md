# TS-076 — Rename `org_id` → `workspace_id` across all modules, RLS, `core.db`

**Status:** done
**Requirement:** Doc §3.2
**Spec(s) updated:** `specs/modules/core.md`
**Module(s):** `core`, multiple
**Severity / Gate:** P0 · Phase 1 (remaining)

## What this builds

The mechanical (but tenant-model-defining) rename that makes TS-075's new
`Workspace` the actual RLS tenant everywhere — every workspace-scoped
table's column, every RLS policy predicate, and `core.db`'s binding
functions (`bind_workspace_context`, formerly org-scoped) switch from
`org_id` to `workspace_id`.

## Implementation

Renamed across every module's `models.py` (`WorkspaceScopedMixin`'s column),
every migration's RLS policy DDL (`rls_statements()`, TS-013), and
`core.db`'s `_SET_WORKSPACE_SQL`/`bind_workspace_context` (TS-012).
No module's own business logic beyond the column/binding name changed.

## Files touched

- `backend/app/core/db.py`
- Every `backend/app/modules/*/models.py` with a workspace-scoped table
- All existing RLS-creating migrations

## Tests

- Full `pytest` suite re-run post-rename (this is a cross-cutting rename;
  correctness is proven by every existing module test still passing).

## Acceptance criteria

- [x] No `org_id` column or reference remains in code or migrations.
- [x] RLS policies bind against `workspace_id` and
      `current_setting('app.workspace_id')`.

## Commit

Predates commit-granular history (PR #10 bulk import).
