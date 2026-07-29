# TS-101 — Enforce MFA at login: challenge tokens, replay guard, re-auth, recovery codes

**Status:** todo
**Requirement:** [R-002 §D](../../specs/requirements/R-002-auth-hardening.md)
**Spec(s) updated:** `specs/modules/auth.md` (to be updated when built)
**Module(s):** `auth`
**Severity / Gate:** P1 · Gate 1

## What this builds

Makes MFA (TS-028) actually gate login instead of being decorative:
currently `login()` issues full access tokens on password alone and never
reads `user.mfa_method` — enrolling in MFA changes nothing about account
security. Also fixes: `mfa_enroll` can be silently re-run with a stolen
access token and no re-authentication (re-enrolling MFA to an attacker's
device), TOTP codes have no replay guard, and there are no recovery codes.

## Current (the defect)

```python
# backend/app/modules/auth/service.py:71 (current)
def login(self, email: str, password: str) -> dict:
    ...
    return self._issue_tokens(user.id, member.workspace_id, member.role, ...)
    # full access tokens issued on password alone; user.mfa_method never read
```

## Implementation (reference plan — not yet built)

Two-stage login: password success returns an `mfa_token` (distinct
`MFA_AUDIENCE`, 5-min TTL) that only grants the right to call
`/auth/mfa/login-verify`, never a real access token:

```python
def login(self, email: str, password: str) -> dict:
    ...
    if user.mfa_totp_secret:
        return {
            "mfa_required": True,
            "mfa_token": sec.mint_mfa_challenge(self.keys, user_id=str(user.id), ttl=timedelta(minutes=5)),
            "method": user.mfa_method,
        }
    return self._issue_tokens(...)

def mfa_login_verify(self, mfa_token: str, code: str) -> dict:
    claims = sec.decode_mfa_challenge(mfa_token, self.keys.public_pem)
    ...
    if not self._consume_totp(user, code) and not self._consume_recovery_code(user, code):
        raise AuthError("invalid_mfa_code")
    return self._issue_tokens(user.id, member.workspace_id, member.role, new_family=True)
```

`decode_access` must verify `aud == ACCESS_AUDIENCE` — otherwise the
challenge and access token types are interchangeable and the whole scheme
is decorative.

Replay guard via `User.mfa_last_used_slot` (rejects reuse of an already-
consumed 30s TOTP window, ±1 slot clock tolerance). Re-enrollment requires
re-authentication with the current password and revokes all sessions
(TS-093) if replacing an existing factor. Enrollment becomes two-step
(`enroll` returns a *pending* secret; `enroll/confirm` with a valid code
promotes it and returns 10 single-use recovery codes, hashed with the same
argon2id helper as passwords). `email`/`sms` MFA methods are rejected with
`501 mfa_method_unavailable` until TS-035/TS-079 wire real delivery — never
silently issuing a TOTP secret for a method the user didn't choose.

## Files touched (planned)

- `backend/app/modules/auth/{service,security,router,models}.py`
- new `mfa_recovery_codes` table + migration

## Tests (planned)

- `backend/tests/modules/auth/test_mfa_login.py` (challenge flow, replay
  rejection, recovery-code consumption)

## Acceptance criteria (R-002 §D, A7–A11)

- [ ] Login for an MFA-enrolled user returns a challenge token, not access
      tokens, until the second factor is verified.
- [ ] A TOTP code cannot be replayed within its own validity window.
- [ ] Re-enrolling MFA requires the current password and revokes existing
      sessions.
- [ ] `email`/`sms` MFA enrollment is rejected (501), not silently
      downgraded to TOTP.

## Commit

Not yet implemented.
