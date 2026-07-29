# TS-075 — Auth model: replace `org`/`org_members` with Workspace/Project hierarchy

**Status:** done
**Requirement:** Doc §5
**Spec(s) updated:** `specs/modules/auth.md`
**Module(s):** `auth`
**Severity / Gate:** P0 · Phase 1 (remaining)

## What this builds

The data-model half of TS-074's spec: removes the flat `org`/`org_members`
tables and introduces `User` + `Workspace`/`WorkspaceMember` +
`Project`/`ProjectMember` + `Invitation`, plus a global `User.is_superadmin`
flag.

## Implementation

New/changed tables in `backend/app/modules/auth/models.py`:
`User` (adds `is_superadmin`), `Workspace`, `WorkspaceMember` (role per
workspace), `Project` (status enum: `planning|tendering|awarded|execution|
closed`), `ProjectMember`, `Invitation` (token, 7-day expiry, email match
required to accept).

## Files touched

- `backend/app/modules/auth/models.py`
- `backend/migrations/versions/` (new migration replacing `org`/`org_members`)

## Tests

- `backend/tests/modules/auth/test_models.py`

## Acceptance criteria

- [x] `org`/`org_members` tables no longer exist; `Workspace`/
      `WorkspaceMember` replace them.
- [x] `User.is_superadmin` exists and defaults to `False`.

## Commit

Predates commit-granular history (PR #10 bulk import).
