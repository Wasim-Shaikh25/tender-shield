# Auth — Spec

**Status:** implemented (email+password, JWT, refresh rotation, RBAC, RLS bind;
TOTP MFA enroll/verify done; phone OTP + Google OIDC deferred; Sign in with Apple
backend callback implemented but requires Apple Developer credentials to enable)
**Requirement refs:** Doc §5, §3.2
**Task refs:** TS-011, TS-012

## Purpose

Trust-critical custom auth: email+password (argon2id), Google OIDC, phone OTP
(MSG91, India-first). Org-scoped RBAC and the RLS binding every other module
relies on.

## Public interface

- **Capabilities published:** `auth.current_principal` (FastAPI dependency),
  `auth.require(min_role)` guard factory.
- **Events emitted:** `auth.user_registered`, `auth.org_created`,
  `auth.refresh_reuse_detected`.
- **API routes:** `/api/auth/signup`, `/login`, `/refresh`, `/logout`,
  `/otp/send`, `/otp/verify`, `/google/callback`, `/apple/authorize`,
  `/apple/callback`, org CRUD + member management.

## Data owned

`users` (including `google_sub`, `apple_id` OIDC links), `orgs`, `org_members`,
`refresh_tokens` (family-tracked), OTP state (Redis).

## Behavior

- **B1:** passwords argon2id (time=3, mem=64MiB, par=2).
- **B2:** access JWT RS256, 15-min TTL, `kid`-headered for key rotation; claims
  `sub`, `org`, `role`, `iss=tendershield`, `aud=tendershield-api`, `jti`.
- **B3:** refresh tokens 30-day, httpOnly Secure cookie, hashed at rest, rotated
  on every use; **reuse detection revokes the whole token family** and audits.
- **B4:** RBAC ranks `viewer<reviewer<estimator<admin<owner`; `require(min_role)`.
- **B5:** every authenticated request executes `SET LOCAL app.org_id` before any
  query (RLS binding, Doc §3.2 — non-negotiable).
- **B6:** rate limits — 5 failed logins/15 min → captcha; OTP 3 sends/10 min,
  5 verify attempts; OTP hash-stored, 5-min TTL.
- **B7:** Google OIDC verifies `iss/aud/email_verified`; links verified emails only.
- **B8:** TOTP MFA optional (mandatory for owner/admin on Pro+, enforcement in billing phase).

## Acceptance criteria

- A1: refresh replay revokes family and returns `reuse_detected`.
- A2: RBAC guard 403s below-rank roles.
- A3: two-org RLS isolation test passes through the whole request stack.

## Out of scope

SSO/SAML (Phase 3), staff/admin auth (separate app, Doc §16).
