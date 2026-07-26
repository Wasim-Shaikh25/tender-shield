# Auth — Spec

**Status:** implemented (email+password, JWT, refresh rotation, RBAC, RLS bind;
TOTP/email/SMS MFA enroll/verify done; phone OTP + Google OIDC deferred; Sign in
with Apple backend callback implemented but requires Apple Developer credentials to
enable)
**Requirement refs:** Doc §5, §3.2, §16
**Task refs:** TS-011, TS-012, TS-074..TS-078

## Purpose

Trust-critical custom auth: email+password (argon2id), Google OIDC, Apple OIDC,
phone OTP (MSG91, India-first). Workspace-scoped RBAC and the RLS binding every
other module relies on. A global `is_superadmin` flag unlocks application-owner
endpoints under `/api/auth/admin/*`.

## Public interface

- **Capabilities published:** `auth.current_principal` (FastAPI dependency),
  `auth.require(min_role)` guard factory, `auth.workspace_factory`.
- **Events emitted:** `auth.user_registered`, `auth.workspace_created`,
  `auth.refresh_reuse_detected`.
- **API routes:**
  - `/api/auth/signup`, `/login`, `/refresh`, `/logout`, `/me`
  - `/api/auth/workspaces` (create/list)
  - `/api/auth/workspaces/{id}/members` (add/list)
  - `/api/auth/workspaces/{id}/projects` (create/list)
  - `/api/auth/projects/{id}/members` (add/list)
  - `/api/auth/invitations` (create) + `/api/auth/invitations/{token}/accept`
  - `/api/auth/mfa/enroll` + `/api/auth/mfa/verify`
  - `/api/auth/otp/send`, `/api/auth/otp/verify`
  - `/api/auth/google/callback`, `/api/auth/apple/authorize`, `/api/auth/apple/callback`
  - `/api/auth/admin/*` (super-admin only: list/create users, set superadmin, list workspaces)

## Data owned

`users` (including `google_sub`, `apple_id`, OIDC links, `is_superadmin`, `mfa_method`,
`mfa_phone`), `workspaces`, `workspace_members`, `projects`, `project_members`,
`invitations`, `refresh_tokens` (family-tracked), OTP state (Redis).

## Behavior

- **B1:** passwords argon2id (time=3, mem=64MiB, par=2).
- **B2:** access JWT RS256, 15-min TTL, `kid`-headered for key rotation; claims
  `sub`, `workspace`, `role`, `is_superadmin`, `iss=tendershield`, `aud=tendershield-api`, `jti`.
- **B3:** refresh tokens 30-day, httpOnly Secure cookie, hashed at rest, rotated
  on every use; **reuse detection revokes the whole token family** and audits.
- **B4:** RBAC ranks `viewer<reviewer<estimator<admin<owner`; `require(min_role)`.
- **B5:** every authenticated request executes `SET LOCAL app.workspace_id` before any
  query (RLS binding, Doc §3.2 — non-negotiable).
- **B6:** rate limits — 5 failed logins/15 min → captcha; OTP 3 sends/10 min,
  5 verify attempts; OTP hash-stored, 5-min TTL.
- **B7:** Google OIDC verifies `iss/aud/email_verified`; links verified emails only.
  Apple OIDC verifies `id_token`, generates client secret from `TS_APPLE_*` keys.
- **B8:** MFA optional: `totp`, `email`, or `sms`; a single TOTP secret is stored on
  the user row and used for verification regardless of delivery channel. Real email/SMS
  delivery is deferred; the chosen method and current code are console-logged.
- **B9:** sign-up creates a bare user plus a default `Workspace` (name from form or
  "Personal") so existing workspace-scoped endpoints keep working.
- **B10:** super-admins bypass workspace checks on `/api/auth/admin/*`; their access
  token carries `is_superadmin=true` and a placeholder `workspace` claim.

## Acceptance criteria

- A1: refresh replay revokes family and returns `reuse_detected`.
- A2: RBAC guard 403s below-rank roles.
- A3: two-workspace RLS isolation test passes through the whole request stack.
- A4: workspace/project CRUD and invitation flow work through the API.
- A5: super-admin endpoints reject non-super-admins with 403.

## Out of scope

SSO/SAML (Phase 3), real email/SMS 2FA delivery, admin AI assistant / Ops Copilot
(Doc §17).
