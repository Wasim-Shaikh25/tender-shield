# TS-077 — Workspace/project CRUD, sharing/invites, super-admin endpoints, 2FA method

**Status:** done
**Requirement:** Doc §5, §16
**Spec(s) updated:** `specs/modules/auth.md`
**Module(s):** `auth`
**Severity / Gate:** P0 · Phase 1 (remaining)

## What this builds

The API surface over TS-075's new models: create/list workspaces and
projects, invite members by email+role, accept invitations, super-admin
endpoints gated by `is_superadmin`, and extends TS-028's TOTP-only MFA to a
selectable method (`totp|email|sms`).

## Implementation

```python
# backend/app/modules/auth/workspaces.py
class WorkspaceAdminError(Exception): ...
class WorkspaceAdmin:
    """Super-admin-only operations: list all users/workspaces, promote a
    user to superadmin — gated by Principal.is_superadmin, not by role rank
    (superadmin is orthogonal to the per-workspace role hierarchy)."""
```

Routes added under `/api/auth/workspaces`, `/api/auth/workspaces/{id}/
members`, `/api/auth/workspaces/{id}/projects`,
`/api/auth/projects/{id}/members`, `/api/auth/invitations`,
`/api/auth/admin/*` (per TS-074's spec).

## Files touched

- `backend/app/modules/auth/{workspaces,router,service,models}.py`

## Tests

- `backend/tests/modules/auth/test_workspaces.py`

## Acceptance criteria

- [x] A non-superadmin caller hitting `/api/auth/admin/*` gets 403.
- [x] An invited user can accept an invitation and gains workspace/project
      membership at the invited role.
- [x] MFA enrollment accepts `totp|email|sms` as the method.

## Commit

Predates commit-granular history (PR #10 bulk import).
