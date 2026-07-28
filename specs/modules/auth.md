# Auth — Spec

**Status:** implemented (email+password, JWT, refresh rotation, RBAC, RLS bind;
TOTP/email/SMS MFA enroll/verify done; password reset via token; phone OTP + Google OIDC deferred; Sign in
with Apple backend callback implemented but requires Apple Developer credentials to
enable)
**Requirement refs:** Doc §5, §3.2, §16
**Task refs:** TS-011, TS-012, TS-074..TS-078, TS-084, TS-085, TS-093

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
  - `/api/auth/forgot-password`, `/reset-password`
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
`invitations`, `password_resets`, `refresh_tokens` (family-tracked), OTP state (Redis).

## Behavior

- **B1:** passwords argon2id (time=3, mem=64MiB, par=2).
- **B2:** access JWT RS256, 15-min TTL, `kid`-headered for key rotation; claims
  `sub`, `workspace`, `role`, `is_superadmin`, `iss=tendershield`, `aud=tendershield-api`, `jti`.
- **B3:** refresh tokens 30-day, httpOnly Secure cookie, hashed at rest, rotated
  on every use; **reuse detection revokes the whole token family** and audits.
- **B4:** RBAC ranks `viewer<reviewer<estimator<admin<owner`; `require(min_role)`.
- **B5:** every authenticated request binds `app.workspace_id` **and**
  `app.user_id` (via `set_config(..., true)`, transaction-scoped) before any
  query (RLS binding, Doc §3.2 — non-negotiable; see `specs/data-model.md` B1
  and `app.core.db` for why both, and why not `SET LOCAL … = :param`).
  `login`, `refresh`, and the existing-user branch of Apple sign-in also bind
  `app.user_id` explicitly, right after the credential/token is verified and
  before the first `WorkspaceMember` query — these are unauthenticated entry
  points where `authenticate()` has not run, and the compound RLS policy on
  `workspace_members` (data-model B1) needs `app.user_id` to find the caller's
  own membership row. `_create_workspace_and_owner` (the single path every
  workspace-creation flow — signup, `create_workspace`, Apple sign-in — must
  go through) binds `app.workspace_id` to the new workspace's own
  pre-generated id before inserting it, because there is no workspace to bind
  to until that insert creates one.
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
- **B11:** forgot-password accepts an email and creates a single-use 15-minute reset token;
  the endpoint returns `ok` even for unknown emails to prevent enumeration. Reset consumes
  the token and updates the user's password hash; expired or reused tokens are rejected.
  Issuing a new reset token invalidates any prior unused one for that user.
- **B12 (dev-only token echo, R-002 §A):** `forgot-password` and `create-invitation`
  return the raw token in the response body only when `TS_DEV_ECHO_TOKENS=true`.
  This is a dev/test convenience for exercising the flow without an email
  provider wired up; app startup raises if `TS_ENV=production` and the flag is
  set, because it is an unauthenticated account-takeover path otherwise. When
  a `notifications.sender` capability is available, both flows deliver the
  token/link by email regardless of the echo setting.
- **B13 (path-scoped authorization, R-001 §A):** every route taking a
  `workspace_id` or `project_id` path parameter (`/workspaces/{id}/members`,
  `/workspaces/{id}/projects`, `/projects/{id}/members`) verifies the caller's
  membership of *that* workspace via `require_workspace_member`/
  `require_project_member` — distinct from `require(min_role)`, which only
  checks the role in the caller's own active (token) workspace. Non-members
  get `404`, not `403`, so a workspace/project's existence is not disclosed.
  Superadmins bypass. Membership guards also re-bind RLS to the workspace
  named in the path, which may differ from the token's `workspace` claim.
- **B14 (last-owner guard):** `add_workspace_member` refuses to demote or
  reassign the sole remaining `owner` of a workspace (`last_owner`, 400) —
  otherwise the workspace is left with nobody able to manage billing, members,
  or deletion.
- **B15 (session revocation on reset, R-002 §B):** `reset-password` revokes
  every refresh-token family belonging to the user in the same transaction as
  the password change, so a session held before the reset (attacker or
  otherwise) does not survive it.

## Acceptance criteria

- A1: refresh replay revokes family and returns `reuse_detected`.
- A2: RBAC guard 403s below-rank roles.
- A3: two-workspace RLS isolation test passes through the whole request stack.
- A4: workspace/project CRUD and invitation flow work through the API.
- A5: super-admin endpoints reject non-super-admins with 403.
- A6: forgot-password returns `ok` for unknown emails and, with
  `TS_DEV_ECHO_TOKENS=true`, a usable token for known emails; reset updates the
  password and invalidates the token. With the default (`false`), no token
  field is present in the response.
- A7: a member of workspace A requesting `/workspaces/{B}/members`,
  `/workspaces/{B}/projects`, or a project under B gets `404`, whether B exists
  or not.
- A8: an admin of workspace A cannot add themselves to workspace B via
  `POST /workspaces/{B}/members` — the request 404s and no membership row is
  created.
- A9: demoting the sole owner of a workspace returns `400 last_owner`.
- A10: a refresh token minted before a password reset returns
  `401 invalid_refresh` afterward.

## Out of scope

SSO/SAML (Phase 3), real email/SMS 2FA delivery, admin AI assistant / Ops Copilot
(Doc §17).
