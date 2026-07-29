# TS-071 — Sign in with Apple (OIDC callback, link verified Apple ID)

**Status:** done
**Requirement:** Doc §5
**Spec(s) updated:** `specs/modules/auth.md`
**Module(s):** `auth`
**Severity / Gate:** P2 · Phase 1 (remaining)

## What this builds

A fourth login method: Sign in with Apple, verifying the Apple-issued ID
token and linking it to an existing/new user the same way Google OIDC
(TS-036, still todo) is planned to. Backend callback is implemented; going
live requires Apple Developer credentials this sandbox doesn't have.

## Implementation

```python
# backend/app/modules/auth/apple.py
class AppleClient:
    """Verifies an Apple-issued ID token against Apple's JWKS and returns
    the verified (sub, email) pair — never trusts a client-supplied email
    unverified."""
```

```python
# backend/app/modules/auth/router.py
class AppleCallbackBody(BaseModel): ...

def apple_authorize(request: Request): ...
def apple_callback(...): ...
```

Issues the same RS256 access/refresh token pair every other login method
produces (TS-011) — no parallel token format for this provider.

## Files touched

- `backend/app/modules/auth/{apple,router,service}.py`

## Tests

- `backend/tests/modules/auth/test_apple.py` (JWKS verification with a
  fixture; not sandbox-verified against real Apple credentials)

## Acceptance criteria

- [x] A valid Apple ID token logs a user in or creates their account.
- [x] The verified `sub`/email pair is never trusted from client input
      directly — only from the verified token.

## Commit

Predates commit-granular history (PR #10 bulk import).
