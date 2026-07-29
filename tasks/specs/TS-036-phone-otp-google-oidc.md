# TS-036 — Phone OTP (MSG91) + Google OIDC login

**Status:** todo (needs creds)
**Requirement:** Doc §5
**Spec(s) updated:** `specs/modules/auth.md` (to be updated when built)
**Module(s):** `auth`
**Severity / Gate:** P2 · Phase 1 MVP

## What this builds

Two additional login methods beyond email+password (TS-011): phone-number
OTP via MSG91 (India-first, per the product's primary market), and Google
OIDC (Sign in with Google) for the common social-login path.

## Implementation (reference plan — not yet built; blocked on provider creds)

- Phone OTP: `/api/auth/otp/request` + `/api/auth/otp/verify`, MSG91 as the
  SMS provider (shared adapter with TS-035 where practical).
- Google OIDC: standard authorization-code flow, verify the ID token
  signature against Google's JWKS, map `sub`+email to an existing/new
  `User` row the same way email+password signup does.
- Both issue the same RS256 access/refresh token pair TS-011 already
  produces — no parallel token format.

## Files touched (planned)

- `backend/app/modules/auth/{router,service,models}.py`
- new `backend/app/modules/auth/oidc_google.py` (mirrors the existing
  `apple.py` Sign-in-with-Apple callback shape)

## Tests (planned)

- OIDC token-verification unit tests with a fixture JWKS.
- OTP request/verify flow tests with a mocked MSG91 client.

## Acceptance criteria

- [ ] A verified phone OTP issues the same token pair as password login.
- [ ] A valid Google ID token logs a user in or creates their account.

## Commit

Not yet implemented — blocked on provider credentials.
