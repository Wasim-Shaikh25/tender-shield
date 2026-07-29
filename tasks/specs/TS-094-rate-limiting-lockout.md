# TS-094 — Rate limiting on auth endpoints + capped per-account lockout

**Status:** done
**Requirement:** [R-002 §C](../../specs/requirements/R-002-auth-hardening.md)
**Spec(s) updated:** `specs/modules/core.md`, `specs/modules/auth.md`
**Module(s):** `core`, `auth`
**Severity / Gate:** P1 · Gate 1

## What this builds

`/auth/login`, `/signup`, `/forgot-password`, `/reset-password` were
completely unthrottled — no rate limiting or lockout existed anywhere in
the codebase. Because password hashing is argon2id (deliberately
expensive), `/login` was also a cheap CPU-exhaustion vector for an
attacker: each guess cost the server more than the attacker.

## Implementation

```python
# backend/app/core/ratelimit.py
"""Fixed-window rate limiting. In-memory by default; Redis-backed when
cache.redis is published (R-016). Keys are (bucket, identity)."""

@dataclass(frozen=True)
class Limit:
    times: int
    seconds: int

class InMemoryLimiter:
    def hit(self, bucket: str, identity: str, limit: Limit) -> bool: ...

def rate_limit(bucket: str, limit: Limit):
    def guard(request: Request) -> None:
        limiter = request.app.state.ctx.registry.require("core.ratelimiter")
        if not limiter.hit(bucket, _client_ip(request), limit):
            raise HTTPException(429, "rate_limited", headers={"Retry-After": str(limit.seconds)})
    return guard
```

Built as `app/core/` infrastructure, not an auth feature, so any module can
declare limits without importing auth (CLAUDE.md §2). Applied per route:

```python
LOGIN_LIMIT = Limit(times=10, seconds=300)
RESET_LIMIT = Limit(times=3, seconds=3600)
SIGNUP_LIMIT = Limit(times=5, seconds=3600)

@router.post("/login", dependencies=[Depends(rate_limit("auth:login", LOGIN_LIMIT))])
def login(...): ...
```

Per-account lockout (distributed guessing can't be stopped by IP limiting
alone):

```python
# auth/models.py — User
failed_logins: Mapped[int] = mapped_column(Integer, default=0)
locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

```python
def login(self, email: str, password: str) -> dict:
    ...
    if user and user.locked_until and user.locked_until > now:
        raise AuthError("account_locked")          # → 423
    if not user or not sec.verify_password(password, user.password_hash):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= 10:
                # Exponential backoff, capped at 60 min — never permanent.
                # Permanent lockout is a denial-of-service handed to the attacker.
                minutes = min(2 ** (user.failed_logins - 10), 60)
                user.locked_until = now + timedelta(minutes=minutes)
            self.s.commit()
        raise AuthError("invalid_credentials")
    user.failed_logins = 0
```

Limits: login 10/5min (IP) + 10 failures→backoff (account); signup 5/hour
(IP); forgot-password 3/hour (IP); reset-password 10/hour (IP); MFA verify
5/5min (user); billing webhook 100/min (IP).

## Files touched

- `backend/app/core/ratelimit.py` (new)
- `backend/app/modules/auth/{router,service,models}.py`
- `backend/migrations/versions/` (new `failed_logins`/`locked_until` columns)

## Tests

- `backend/tests/test_core_ratelimit.py`
- `backend/tests/modules/auth/test_service.py::test_account_lockout_capped_backoff`

## Acceptance criteria (R-002 §C, A5, A6)

- [x] Every listed auth route enforces its rate limit and returns 429 with
      `Retry-After` when exceeded.
- [x] Account lockout backs off exponentially but is capped at 60 minutes —
      never permanent.

## Commit

Predates commit-granular history (PR #10 bulk import).
