# Auth — Spec

**Status:** re-architecture in progress (TS-163): account is the top-level identity; workspace
is created explicitly after login; platform-only registration/login; email + mobile verification;
OTP required on every login. Social login (Google/Apple) removed.
**Requirement refs:** Doc §5, §3.2, §16; user request (account-first, OTP login)
**Task refs:** TS-011, TS-012, TS-035, TS-036, TS-074..TS-078, TS-079, TS-106, TS-163, TS-171

## Purpose

Trust-critical custom auth: email+password (argon2id), OTP-based verification and
login, workspace-scoped RBAC and the RLS binding every other module relies on.
Account is the top-level identity; a user signs up once, verifies email and mobile,
then creates workspaces after login. A global `is_superadmin` flag unlocks
application-owner endpoints under `/api/auth/admin/*`.

## Public interface

- **Capabilities published:** `auth.current_principal` (FastAPI dependency),
  `auth.require(min_role)` guard factory, `auth.workspace_factory`.
- **Events emitted:** `auth.user_registered`, `auth.workspace_created`,
  `auth.refresh_reuse_detected`.
- **API routes:**
  - `/api/auth/signup` (account-only; requires org_name, phone, city, dob, password, confirm_password)
  - `/api/auth/verify-email` (POST token)
  - `/api/auth/verify-mobile` (POST token)
  - `/api/auth/resend-verification` (account context)
  - `/api/auth/login`, `/api/auth/mfa/challenge`, `/api/auth/refresh`, `/api/auth/logout`, `/api/auth/me`
  - `/api/auth/forgot-password`, `/api/auth/reset-password`
  - `/api/auth/settings` (GET/PUT profile), `/api/auth/settings/password` (POST change password)
  - `/api/auth/export` (POST) — GDPR/DPDP data portability export
  - `/api/auth/account` (DELETE) — GDPR/DPDP account erasure
  - `/api/auth/workspaces` (create/list)
  - `/api/auth/workspaces/{id}/members` (add/list/change-role/remove)
  - `/api/auth/workspaces/{id}/projects` (create/list)
  - `/api/auth/projects/{id}/members` (add/list)
  - `/api/auth/invitations` (create/list) + `/api/auth/invitations/{token}/accept`
  - `/api/auth/invitations/{id}` (revoke)
  - `/api/auth/mfa/enroll` + `/api/auth/mfa/verify`
  - `/api/auth/workspaces/{id}/switch`
  - `/api/auth/admin/*` (super-admin only: list/create users, set superadmin, list workspaces)
  - `/api/auth/admin/users/search` (super-admin: search by email, phone, org_name, workspace name)
  - `/api/auth/admin/users/{id}` (super-admin: user detail, including workspaces and last login)
  - `/api/auth/admin/users/{id}/suspend` (super-admin: suspend account)
  - `/api/auth/admin/users/{id}/unsuspend` (super-admin: restore account)
  - `/api/auth/admin/users/{id}` (DELETE — super-admin: delete user account)
  - `/api/auth/admin/workspaces/{id}` (super-admin: workspace detail, members, invoices)
  - `/api/auth/admin/workspaces/{id}/plan` (super-admin: change workspace plan)
  - `/api/auth/admin/dashboard` (super-admin: KPI summary)
  - `/api/auth/admin/audit-log` (super-admin: search audit log by workspace/action/object/actor/date)

## Data owned

`users` (`email`, `phone` unique, `password_hash`, `org_name`, `dob`, `city`,
`email_verified`, `mobile_verified`, `is_superadmin`, `suspended_at`, `suspended_by`,
`mfa_method`, `mfa_phone`),
`mobile_verifications`, `workspaces`, `workspace_members`, `projects`, `project_members`,
`invitations`, `password_resets`, `refresh_tokens` (family-tracked).

## Behavior

- **B1:** passwords argon2id (time=3, mem=64MiB, par=2) and must contain ≥ 1 upper,
  ≥ 1 lower, ≥ 1 digit, and ≥ 1 special character; length ≥ 8.
- **B2:** access JWT RS256, 15-min TTL, `kid`-headered for key rotation; claims
  `sub`, `workspace`, `role`, `is_superadmin`, `email_verified`, `mobile_verified`, `iss=tendershield`, `aud=tendershield-api`, `jti`.
  The `workspace` claim is a sentinel UUID when no workspace is selected (account-level session).
- **B3:** refresh tokens 30-day, httpOnly Secure cookie, hashed at rest, rotated
  on every use; **reuse detection revokes the whole token family** and audits.
  Refresh-token rows store the selected `workspace_id` so `/api/auth/refresh` preserves
  the user's current workspace instead of falling back to an arbitrary membership.
- **B4:** RBAC ranks `viewer<reviewer<estimator<admin<owner`; `require(min_role)`.
- **B5:** every authenticated request executes `SET LOCAL app.workspace_id` before any
  query (RLS binding, Doc §3.2 — non-negotiable). A nil `workspace` claim uses a
  sentinel UUID and blocks workspace-scoped reads/writes until the user selects/creates a workspace.
- **B6:** rate limits — 5 failed logins/15 min → account lockout; OTP 3 sends/10 min,
  5 verify attempts; OTP hash-stored, 5-min TTL.
- **B8:** Login always returns an OTP challenge. `AuthService` generates a 6-digit
  OTP, stores its hash on the user row with a 5-minute TTL, and sends it through the
  `notifications.sender` adapter. The client posts `/mfa/challenge` with the
  `mfa_token` and the 6-digit code to receive tokens. In dev/tests the code is
  returned in the response body. TOTP enrollment remains optional for account
  recovery but the per-login OTP is mandatory.
- **B9:** sign-up creates only a `User`; it does **not** create a workspace. The user
  must be verified (email + mobile) before any workspace-scoped action.
- **B10:** super-admins bypass workspace checks on `/api/auth/admin/*`; their access
  token carries `is_superadmin=true` and a placeholder `workspace` claim.
- **B11:** forgot-password accepts an email and creates a single-use 15-minute reset token;
  the endpoint returns `ok` even for unknown emails to prevent enumeration. Reset consumes
  the token and updates the user's password hash; expired or reused tokens are rejected.
- **B12 — Refresh token cookie:** `/login` returns an `mfa_token`; `/mfa/challenge`
  returns an `access_token` in JSON and sets `refresh_token` as an `httpOnly`, `Secure`
  (prod), `SameSite=Lax` cookie. `/api/auth/refresh` reads the cookie, rotates the
  stored token family, and sets a new cookie. `/api/auth/logout` clears the cookie and
  revokes the family.
- **B14 — Workspace switcher:** `GET /api/auth/workspaces` lists the user's workspace
  memberships. `POST /api/auth/workspaces/{id}/switch` returns tokens bound to the
  chosen workspace (and the same workspace ID in the new cookie).
- **B15 — Registration fields:** email, phone (unique), password, confirm password,
  org/company name, date of birth (optional), city.
- **B16 — Account lockout:** 5 failed login attempts within 15 minutes lock the account
  for 15 minutes.
- **B17 — Invitation tokens:** invitation tokens are generated with `secrets.token_urlsafe`
  and stored as a SHA-256 hash. In the dev/test fallback the token is prefixed with its
  workspace_id (`<workspace_id>:<random>`) so `accept_invitation` can bind RLS to the
  invitation's workspace before lookup. The random portion is hashed before lookup.
- **B18 — No social login:** Google/Apple OIDC routes and settings are removed.
- **B19 — Account settings:** `/api/auth/settings` returns/updates the current user's
  profile (org_name, phone, dob, city). `/api/auth/settings/password` changes the
  password after re-authentication.
- **B20 — Team management:** workspace `admin` and `owner` roles can list members,
  change a member's role, and remove a member. An `admin` cannot promote a member
  above their own role and cannot remove themselves.
- **B21 — Invitation lifecycle:** `GET /api/auth/invitations` lists pending
  invitations. `DELETE /api/auth/invitations/{id}` removes a pending invitation,
  revoking the token. Only `admin`+ roles can list, create, or revoke invitations.
- **B22 — Seat limits:** `add_workspace_member`, `create_invitation`, and
  `accept_invitation` enforce the workspace plan's seat cap. A pending invitation
  reserves a seat until it is revoked, expires, or accepted. The canonical seat
  limits are shared by the billing module through the registry (`billing.seat_limits`).
- **B23 — Account suspension:** super-admins can suspend a user via
  `POST /api/auth/admin/users/{id}/suspend`. A suspended user cannot log in; any
  active refresh tokens are revoked. `POST .../unsuspend` restores access. Suspension
  sets `suspended_at` and records `suspended_by`; login checks `suspended_at` before
  password verification and returns `account_suspended`.
- **B24 — Admin user search:** super-admins can search users by email, phone,
  `org_name`, or workspace name. Results are paginated and never expose password
  hashes, MFA secrets, or verification tokens.
- **B25 — Admin user detail and deletion:** super-admins can view a user, their
  workspaces, and delete the account. Deletion follows the same workspace-scoped
  erasure flow as self-service `DELETE /api/auth/account`.
- **B26 — Admin workspace plan change:** super-admins can change a workspace plan
  through `POST /api/auth/admin/workspaces/{id}/plan`. The change is logged to the
  audit trail and reflected in the workspace's billing status.
- **B27 — Admin dashboard KPIs:** `GET /api/auth/admin/dashboard` returns counts of
  total users, suspended users, active workspaces, pending verifications, and
  recent sign-ups (last 30 days).
- **B28 — Email change with verification:** `POST /api/auth/settings/email` requests a
  change to a new email and sends a verification token. `POST /api/auth/settings/email/verify`
  confirms the change and updates the user's email. Duplicate emails are rejected.

## Acceptance criteria

- A1: refresh replay revokes family and returns `reuse_detected`.
- A2: RBAC guard 403s below-rank roles.
- A3: two-workspace RLS isolation test passes through the whole request stack.
- A4: workspace/project CRUD and invitation flow work through the API after user
  verifies email/mobile and creates a workspace.
- A5: super-admin endpoints reject non-super-admins with 403.
- A6: forgot-password returns `ok` for unknown emails and a usable token for known emails;
  reset updates the password and invalidates the token.
- A7: `/mfa/challenge` response sets an `httpOnly` `refresh_token` cookie and the JSON body does not.
- A8: `/auth/refresh` uses the cookie, issues a new access token, and rotates the cookie.
- A9: every login returns `mfa_required` with a valid `mfa_token`; the correct per-login OTP
  returns tokens. TOTP enrollment still works for recovery.
- A10: `/auth/workspaces` lists all user memberships; switching workspace issues tokens for it.
- A11: weak/short passwords missing uppercase, lowercase, digit, or special characters are
  rejected at signup and reset.
- A12: 5 failed logins lock the account for 15 minutes.
- A13: account-only sign-up creates no workspace; `/auth/workspaces` returns `[]` until the user
  explicitly creates one.
- A14: `POST /api/auth/workspaces/{id}/members` rejects principals whose workspace does not match
  `{id}` (super-admins excepted).
- A15: `POST /api/auth/resend-verification` returns a generic status and never exposes the raw
  verification token.
- A16: `PUT` and `DELETE /api/auth/workspaces/{id}/members/{user_id}` enforce admin+ role,
  prevent self-management, and prevent assigning a role above the actor's own role.
- A17: `GET /api/auth/invitations` and `DELETE /api/auth/invitations/{id}` allow admin+ roles
  to list and revoke pending invitations.
- A18: `POST /api/auth/workspaces/{id}/switch` rotates the refresh token and persists the new
  refresh-token row before returning tokens.
- A19: sign-up rejects mismatched `confirm_password` and missing required fields.
- A20: `GET /api/auth/workspaces/{id}/members` and `GET /api/auth/projects/{id}/members` reject
  callers who are not members of the target workspace (super-admins excepted).
- A21: `create_invitation` and `accept_invitation` verify that a supplied `project_id` belongs to
  the invitation's workspace.
- A22: invitation tokens are stored as a SHA-256 hash; only the creator/email sender
  sees the raw token once.
- A23: TOTP enrollment returns a pending secret and only sets `mfa_method=totp` after
  the first code is verified.
- A24: `/api/auth/settings` returns and updates `org_name`, `phone`, `dob`, `city`.
- A25: `/api/auth/settings/password` requires current password and rejects reused/weak passwords.
- A26: sign-up sends separate email and mobile verification OTPs; both must be verified before
  login returns a usable access token.
- A27: login always issues an account-level `mfa_token` (no workspace selected). After MFA,
  `/api/auth/refresh` and `/api/auth/workspaces/{id}/switch` preserve or return a workspace-bound
  token; a user with no workspaces gets an account-level access token and can call
  `/api/auth/workspaces` and `/api/auth/workspaces` create.
- A28: `add_workspace_member`, `create_invitation`, and `accept_invitation` reject
  requests that would exceed the workspace plan's seat limit with `seat_limit_exceeded`.
- A29: `POST /api/auth/export` returns a portable, machine-readable JSON export of the
  caller's profile plus every workspace-scoped row they own or are a member of, and all
  user-owned auth rows (refresh tokens, password resets, verifications). Used for GDPR/DPDP
  portability requests.
- A30: `DELETE /api/auth/account` requires the caller's password and `confirm=true`. It
  deletes the user row and, before cascading, explicitly erases all workspace-scoped rows
  in any workspace the user belongs to. This implements the GDPR/DPDP right to erasure.
- A31: `POST /api/auth/admin/users/{id}/suspend` revokes the user's refresh tokens
  and subsequent logins return `account_suspended`.
- A32: `GET /api/auth/admin/users/search` and `GET /api/auth/admin/users` never
  include `password_hash`, `mfa_*` secrets, or verification token hashes.
- A33: `GET /api/auth/admin/dashboard` returns total users, suspended users,
  active workspaces, pending verifications, and recent sign-ups.
- A34: `POST /api/auth/admin/workspaces/{id}/plan` updates the workspace plan and
  logs an `admin.workspace_plan_changed` audit event.

## Out of scope

SSO/SAML (Phase 3), real email/SMS 2FA delivery, admin AI assistant / Ops Copilot
(Doc §17).
