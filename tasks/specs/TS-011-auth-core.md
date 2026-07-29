# TS-011 — `auth` module: email+password, RS256 JWT, rotating refresh

**Status:** done
**Requirement:** Doc §5
**Spec(s) updated:** `specs/modules/auth.md`
**Module(s):** `auth`
**Severity / Gate:** P0 · Phase 1 MVP

## What this builds

The first identity primitive: argon2id password hashing, short-lived RS256
access tokens, and rotating refresh tokens with reuse detection — the
credential layer every other module's `auth.current_principal` dependency
sits on.

## Implementation

```python
# backend/app/modules/auth/security.py
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ALGO = "RS256"
ISSUER = "tendershield"
AUDIENCE = "tendershield-api"

def hash_password(password: str) -> str: ...
def verify_password(password: str, hashed: str) -> bool: ...
```

```python
# backend/app/modules/auth/refresh.py
def new_refresh() -> tuple[str, str]: ...      # (raw token, hash) pair
def hash_token(raw: str) -> str: ...

class RefreshVerdict(StrEnum): ...              # VALID | EXPIRED | REUSED | ...
def evaluate_refresh(row: RefreshRowLike | None, now: datetime) -> RefreshVerdict: ...
```

Access tokens are 15-minute RS256 JWTs (`ISSUER`/`AUDIENCE` checked on
verify); refresh tokens are opaque, stored hashed, rotated on every use, and
reuse of an already-rotated token revokes the whole chain and publishes
`auth.refresh_reuse_detected`.

## Files touched

- `backend/app/modules/auth/{security,refresh,router,service,models}.py`

## Tests

- `backend/tests/modules/auth/test_security.py`, `test_refresh.py`

## Acceptance criteria

- [x] Passwords are hashed with argon2id, never stored/logged in plaintext.
- [x] Access tokens are RS256, 15-minute expiry, issuer/audience checked.
- [x] A rotated refresh token reused a second time is rejected and revokes
      the chain.

## Commit

Predates commit-granular history (PR #10 bulk import).
