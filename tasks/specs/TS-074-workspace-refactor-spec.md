# TS-074 — Spec for workspace/project tenant refactor + super admin

**Status:** done
**Requirement:** Doc §3.2, §5
**Spec(s) updated:** `specs/workspace-and-admin-refactor.md` (superseded —
  see below), `specs/modules/auth.md`
**Module(s):** `auth`
**Severity / Gate:** P1 · Phase 1 (remaining)

## What this builds

The design doc for replacing the hard-coded `org` tenant with a `User →
Workspace → Project` hierarchy plus a global super-admin role — written
*before* TS-075..078 implement it, per CLAUDE.md §1.2 ("spec before
implementation").

## Implementation

`specs/workspace-and-admin-refactor.md` (original spec, now superseded by
this task-file layer per TS-126's restructure — its content is preserved
below rather than duplicated across TS-075..078's files):

- **Public interface:** `POST/GET /api/auth/workspaces`, `.../members`,
  `.../projects`, `/api/auth/projects/{id}/members`, `/api/auth/mfa/enroll`
  (totp|email|sms), admin routes under `/api/auth/admin/*`
  (`GET /users`, `GET /workspaces`, `POST /users`, `POST /users/{id}/superadmin`).
- **Data owned:** `users`, `workspaces`, `workspace_members`, `projects`,
  `project_members`, `invitations`, `refresh_tokens`.
- **Behavior:** `Workspace` is the RLS/billing tenant (every workspace-scoped
  table carries `workspace_id` + RLS policy). `Project` is a lifecycle
  container (`planning|tendering|awarded|execution|closed`). `User.is_superadmin`
  bypasses RLS on `/api/admin/*`. Sign-up creates a bare user + default
  workspace. Invitations are token-based, 7-day expiry, accepted via
  `POST /api/auth/invitations/{token}/accept`.
- **Out of scope (at spec time):** real email/SMS 2FA delivery (TS-079),
  admin AI assistant (Part 17), project-level RLS/billing.

## Files touched

- `specs/workspace-and-admin-refactor.md`

## Tests

None — design spec, implemented by TS-075..078.

## Acceptance criteria

- [x] The spec exists before any refactor code lands (TS-075 is the next
      task chronologically).
- [x] A1-A4 acceptance criteria are stated and later verified by TS-078.

## Commit

Predates commit-granular history (PR #10 bulk import).
