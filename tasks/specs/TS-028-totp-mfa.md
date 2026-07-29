# TS-028 — TOTP MFA (pyotp): enroll (secret+otpauth URI) + verify

**Status:** done
**Requirement:** Doc §5
**Spec(s) updated:** `specs/modules/auth.md`
**Module(s):** `auth`
**Severity / Gate:** P1 · Phase 1 MVP

## What this builds

Time-based one-time-password MFA as a second auth factor: enrollment
(secret + `otpauth://` URI for a QR code) and verification.

## Implementation

```python
# backend/app/modules/auth/mfa.py
def new_secret() -> str: ...
def provisioning_uri(secret: str, account: str) -> str: ...
def verify(secret: str, code: str) -> bool: ...
```

Mounted at `/api/auth/mfa/enroll` + `/api/auth/mfa/verify`; the secret is
stored encrypted-at-rest on the user row, never logged.

## Files touched

- `backend/app/modules/auth/{mfa,router,models}.py`

## Tests

- `backend/tests/modules/auth/test_mfa.py`

## Acceptance criteria

- [x] Enrollment returns a secret + valid `otpauth://` provisioning URI.
- [x] `verify()` accepts a correct TOTP code and rejects an incorrect one.

## Commit

Predates commit-granular history (PR #10 bulk import).
