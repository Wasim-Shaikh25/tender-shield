# Workspace, Project, and Super-Admin Refactor — Spec

**Status:** in_progress  
**Requirement refs:** Doc §3.2, §5, §11, §16, §17  
**Task refs:** TS-074..TS-078

## Purpose

Remove the hard-coded `org` tenant and replace it with a flexible `User →
Workspace → Project` hierarchy plus a global super-admin role. Sign-up creates a
bare user and a default `Workspace` so existing workflows keep working; users can
create additional workspaces and projects later and invite collaborators.

## Public interface

- `auth` capabilities remain (`auth.keys`, `auth.current_principal`, `auth.require`).
- New auth routes:
  - `POST /api/auth/workspaces` — create a workspace (viewer+ after first one).
  - `GET /api/auth/workspaces` — list user workspaces.
  - `POST /api/auth/workspaces/{id}/members` — invite by email/role.
  - `GET /api/auth/workspaces/{id}/members` — list members.
  - `POST /api/auth/workspaces/{id}/projects` — create a project.
  - `GET /api/auth/workspaces/{id}/projects` — list projects.
  - `POST /api/auth/projects/{id}/members` — invite by email/role.
  - `GET /api/auth/projects/{id}/members` — list members.
  - `POST /api/auth/mfa/enroll` — choose totp|email|sms.
  - `POST /api/auth/mfa/verify` — verify an MFA code.
- Admin routes (super-admin only, mounted under `/api/auth/admin/`):
  - `GET /admin/users`
  - `GET /admin/workspaces`
  - `POST /admin/users`
  - `POST /admin/users/{id}/superadmin`

## Data owned

`auth` owns: `users`, `workspaces`, `workspace_members`, `projects`,
`project_members`, `invitations`, `refresh_tokens`.

## Behavior

- `Workspace` is the RLS/billing tenant. Every workspace-scoped table carries
  `workspace_id` and RLS policy `workspace_id = current_setting('app.workspace_id')::uuid`.
- `Project` is a lifecycle container under a workspace. `Project` status enum:
  `planning`, `tendering`, `awarded`, `execution`, `closed`.
- `User` has a global `is_superadmin` flag. Super-admins bypass RLS on `/api/admin/*`.
- Sign-up creates a bare user and a default `Workspace` named from the sign-up
  form (or "Personal"). The access token carries that workspace.
- Invitations are token-based, expire in 7 days, and are accepted by an
  authenticated user via `POST /api/auth/invitations/{token}/accept`.
- MFA supports `totp` (existing), `email`, and `sms` methods; the secret is stored
  on the user row and the delivery channel is logged to console until a real
  email/SMS provider is wired.

## Acceptance criteria

- A1: `pytest` passes after `org_id` is renamed to `workspace_id` across all
  modules and migrations.
- A2: Sign-up creates a user and a default workspace; the returned token carries
  that workspace.
- A3: Super-admin endpoints list/create users and list workspaces; non-super-admins
  receive 403.
- A4: Existing pre-bid flow still works through workspace-scoped RLS.

## Out of scope

- Real email/SMS 2FA delivery (use console logging).
- Admin AI assistant / Ops Copilot (Part 17).
- Project-level RLS or per-project billing.
