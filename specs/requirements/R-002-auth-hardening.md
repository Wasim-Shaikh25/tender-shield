# R-002 — Auth hardening: reset tokens, session revocation, rate limiting, MFA

**Status:** draft
**Severity:** P0 (reset-token echo) / P1 (the rest)
**Requirement refs:** Doc §5, §11.3
**Task refs:** TS-085, TS-093, TS-094, TS-101
**Task files:** code-level detail (current-vs-target snippets, file:line, files touched, tests) now lives per-task, split out by TS-126's restructure: [TS-085](../../tasks/specs/TS-085-gate-dev-token-echo.md), [TS-093](../../tasks/specs/TS-093-revoke-sessions-on-reset.md), [TS-094](../../tasks/specs/TS-094-rate-limiting-lockout.md), [TS-101](../../tasks/specs/TS-101-enforce-mfa-at-login.md). This document stays the business/behavior-level record (purpose, target behavior, acceptance criteria).

**Gap refs:** `docs/GAP_ANALYSIS.md` §1.5–§1.8, §3.5
**Specs to update:** `specs/modules/auth.md`

## Purpose

Four independent defects in the authentication surface. The first is
unauthenticated account takeover and must ship first; the rest close the gap
between "MFA and password reset exist as endpoints" and "MFA and password reset
protect accounts".

---

## Part A — Stop echoing the reset token (TS-085, P0)

### A.1 Current

```python
# backend/app/modules/auth/service.py:491
def forgot_password(self, email: str) -> dict:
    email = email.strip().lower()
    user = self.s.scalar(select(User).where(User.email == email))
    if not user:
        return {"ok": True}
    raw, token_hash = rf.new_refresh()
    expires_at = datetime.now(UTC) + timedelta(minutes=15)
    self.s.add(PasswordReset(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    self.s.commit()
    # TODO: wire email delivery; return token for dev/test until delivery exists
    return {"ok": True, "token": raw}          # ← returned to an UNAUTHENTICATED caller
```

`router.py:158` returns this dict verbatim. Anyone who knows a user's email
address reads the token out of the response and resets that password. Every
account in every deployment is takeable.

`create_invitation` (`service.py:416`) has the same shape — admin-only, so P2,
but it moves to the same switch.

### A.2 Target

Add an explicit, loudly-named dev setting and make production refuse it.

```python
# backend/app/core/config.py

    env: str = "dev"

    # DEV ONLY. Returns password-reset / invitation tokens in the HTTP response
    # so local flows work without an email provider. Enabling this in production
    # is unauthenticated account takeover (R-002 §A.1) — startup refuses it.
    dev_echo_tokens: bool = False

    def model_post_init(self, __context) -> None:
        if self.env == "production" and self.dev_echo_tokens:
            raise ValueError(
                "TS_DEV_ECHO_TOKENS must be false when TS_ENV=production "
                "(it returns password-reset tokens to unauthenticated callers)"
            )
```

The service takes the flag and never decides policy itself:

```python
# backend/app/modules/auth/service.py

class AuthService:
    def __init__(self, session, keys, *, ..., echo_tokens: bool = False, notifier=None):
        ...
        self._echo_tokens = echo_tokens
        self._notifier = notifier          # notifications.sender capability, optional

    def forgot_password(self, email: str) -> dict:
        email = email.strip().lower()
        user = self.s.scalar(select(User).where(User.email == email))
        if not user:
            return {"ok": True}            # constant response — no enumeration
        raw, token_hash = rf.new_refresh()
        self.s.add(
            PasswordReset(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + timedelta(minutes=15),
            )
        )
        self.s.commit()
        self._send_reset_email(user.email, raw)
        return {"ok": True, "token": raw} if self._echo_tokens else {"ok": True}
```

Delivery goes through the existing `notifications` sender protocol
(`notifications/sender.py:20`) resolved from the registry, so auth never imports
notifications:

```python
def _send_reset_email(self, email: str, raw_token: str) -> None:
    if self._notifier is None:
        logger.warning("password reset requested but no notifications sender is available")
        return
    self._notifier.send(Message(
        channel="email",
        to=email,
        subject="Reset your TenderShield password",
        body=f"{self._app_url}/reset-password?token={raw_token}\n\nThis link expires in 15 minutes.",
    ))
```

Wire the capability in `auth/router.py::_service`:

```python
return AuthService(
    session, keys,
    access_ttl_min=settings.access_ttl_minutes,
    refresh_ttl_days=settings.refresh_ttl_days,
    apple_client=apple_client,
    echo_tokens=settings.dev_echo_tokens,
    notifier=request.app.state.ctx.registry.get("notifications.sender"),
)
```

`notifications/module.py` must publish `notifications.sender` (it currently
publishes only the digest capability — check and add).

### A.3 Also required

- **Invalidate outstanding resets** when a new one is issued, so a stale link in
  an old email cannot be replayed:
  ```python
  self.s.execute(
      update(PasswordReset)
      .where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None))
      .values(used_at=datetime.now(UTC))
  )
  ```
- **`.env.example`** documents `TS_DEV_ECHO_TOKENS=false` with the warning.
- The frontend `/forgot-password` page stops displaying the token
  (`app/forgot-password/page.tsx`) and shows "check your email" unconditionally.

---

## Part B — Revoke sessions on password reset (TS-093)

### B.1 Current

```python
# backend/app/modules/auth/service.py:503
def reset_password(self, token: str, new_password: str) -> dict:
    ...
    user.password_hash = sec.hash_password(new_password)
    row.used_at = datetime.now(UTC)
    self.s.commit()
    return {"ok": True}
```

Refresh-token families are untouched. An attacker holding a session keeps it
after the victim resets — which defeats the main reason people reset passwords.

### B.2 Target

```python
    user.password_hash = sec.hash_password(new_password)
    row.used_at = datetime.now(UTC)
    self._revoke_all_sessions(user.id)      # ← every family, every device
    self.s.commit()
    return {"ok": True}

def _revoke_all_sessions(self, user_id) -> None:
    """Password change invalidates every issued session (Doc §5).

    Access tokens are stateless and live up to `access_ttl_minutes` (15), so
    revocation is eventual for those; refresh families die immediately, which
    caps an attacker's remaining window at one access-token TTL.
    """
    self.s.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == uuid.UUID(str(user_id)), RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
```

Apply the same call on: successful `reset_password`, MFA re-enrollment
(Part D), and a future `POST /auth/logout-all`.

### B.3 Session management endpoints

```
GET    /api/auth/sessions          → [{family_id, created_at, last_used_at, user_agent, ip}]
DELETE /api/auth/sessions/{family} → revoke one device
POST   /api/auth/logout-all        → revoke every family
```

Requires two nullable columns on `refresh_tokens` (`user_agent`, `ip`) captured
at issue time. Also add a pruning job — `RefreshToken` rows are never deleted
today and the table grows without bound:

```sql
DELETE FROM refresh_tokens WHERE expires_at < now() - interval '30 days';
```

---

## Part C — Rate limiting and lockout (TS-094)

### C.1 Current

`grep -rn "rate.?limit\|lockout\|throttle" backend/app` returns nothing.
`/auth/login`, `/auth/signup`, `/auth/forgot-password`, `/auth/reset-password`
are unthrottled. Because password hashing is argon2id, `/auth/login` is also a
cheap CPU-exhaustion vector: each guess costs the server far more than the
attacker.

### C.2 Target — a core middleware, not an auth feature

Rate limiting is infrastructure (`app/core/`), so any module can declare limits
without importing auth.

```python
# backend/app/core/ratelimit.py

"""Fixed-window rate limiting. In-memory by default; Redis-backed when
`cache.redis` is published (R-016). Keys are (bucket, identity) where identity
is the client IP for anonymous routes and the user id once authenticated."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request


@dataclass(frozen=True)
class Limit:
    times: int
    seconds: int


class InMemoryLimiter:
    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], list[float]] = defaultdict(list)

    def hit(self, bucket: str, identity: str, limit: Limit) -> bool:
        now = time.monotonic()
        window = self._hits[(bucket, identity)]
        window[:] = [t for t in window if now - t < limit.seconds]
        if len(window) >= limit.times:
            return False
        window.append(now)
        return True


def rate_limit(bucket: str, limit: Limit):
    def guard(request: Request) -> None:
        limiter = request.app.state.ctx.registry.require("core.ratelimiter")
        identity = _client_ip(request)
        if not limiter.hit(bucket, identity, limit):
            raise HTTPException(429, "rate_limited", headers={"Retry-After": str(limit.seconds)})

    return guard


def _client_ip(request: Request) -> str:
    # Trust X-Forwarded-For only behind a known proxy (TS_TRUSTED_PROXIES).
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "-")
```

Applied per route:

```python
# backend/app/modules/auth/router.py
from app.core.ratelimit import Limit, rate_limit

LOGIN_LIMIT = Limit(times=10, seconds=300)     # per IP
RESET_LIMIT = Limit(times=3, seconds=3600)
SIGNUP_LIMIT = Limit(times=5, seconds=3600)


@router.post("/login", dependencies=[Depends(rate_limit("auth:login", LOGIN_LIMIT))])
def login(...): ...
```

### C.3 Per-account lockout

IP limiting alone does not stop a distributed guess against one account. Add a
counter on the user:

```python
# auth/models.py — User
failed_logins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

```python
def login(self, email: str, password: str) -> dict:
    user = self.s.scalar(select(User).where(User.email == email.strip().lower()))
    now = datetime.now(UTC)
    if user and user.locked_until and user.locked_until > now:
        raise AuthError("account_locked")          # → 423
    if not user or not user.password_hash or not sec.verify_password(password, user.password_hash):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= 10:
                # Exponential backoff, capped. Never permanent — permanent
                # lockout is a denial-of-service handed to the attacker.
                minutes = min(2 ** (user.failed_logins - 10), 60)
                user.locked_until = now + timedelta(minutes=minutes)
            self.s.commit()
        raise AuthError("invalid_credentials")
    user.failed_logins = 0
    user.locked_until = None
    ...
```

Note the deliberate choice: lockout is time-boxed and capped at 60 minutes.
Permanent lockout converts a guessing attack into an account-denial attack.

### C.4 Limits table

| Route | Bucket | Limit | Key |
|---|---|---|---|
| `POST /auth/login` | `auth:login` | 10 / 5 min | IP |
| `POST /auth/login` (per account) | — | 10 failures → backoff | user |
| `POST /auth/signup` | `auth:signup` | 5 / hour | IP |
| `POST /auth/forgot-password` | `auth:reset` | 3 / hour | IP |
| `POST /auth/reset-password` | `auth:reset-confirm` | 10 / hour | IP |
| `POST /auth/mfa/verify` | `auth:mfa` | 5 / 5 min | user |
| `POST /billing/webhooks/razorpay` | `billing:webhook` | 100 / min | IP |

---

## Part D — Make MFA real (TS-101)

### D.1 Current

```python
# backend/app/modules/auth/service.py:71
def login(self, email: str, password: str) -> dict:
    ...
    return self._issue_tokens(user.id, member.workspace_id, member.role, ...)
    # ← full access tokens issued on password alone; user.mfa_method never read
```

`POST /auth/mfa/verify` requires an already-valid access token and returns a bare
boolean (`service.py:483`) that nothing consumes. Enrolling in MFA changes
nothing about account security. Two further problems:

- `mfa_enroll` (`service.py:468`) overwrites `mfa_totp_secret` on any call with
  no re-authentication — a stolen access token can re-enroll MFA to the
  attacker's device.
- No replay guard: a TOTP code stays valid for its whole window.
- No recovery codes: a lost authenticator is a lost account.

### D.2 Target — two-stage login

```python
def login(self, email: str, password: str) -> dict:
    ...credential check, lockout check...
    if user.mfa_totp_secret:
        # Password proved; second factor outstanding. This token grants nothing
        # except the right to call /auth/mfa/login-verify (Doc §5).
        return {
            "mfa_required": True,
            "mfa_token": sec.mint_mfa_challenge(self.keys, user_id=str(user.id), ttl=timedelta(minutes=5)),
            "method": user.mfa_method,
        }
    return self._issue_tokens(...)


def mfa_login_verify(self, mfa_token: str, code: str) -> dict:
    claims = sec.decode_mfa_challenge(mfa_token, self.keys.public_pem)   # raises on bad/expired
    user = self.s.get(User, uuid.UUID(claims["sub"]))
    if not user or not user.mfa_totp_secret:
        raise AuthError("mfa_not_enrolled")
    if not self._consume_totp(user, code) and not self._consume_recovery_code(user, code):
        raise AuthError("invalid_mfa_code")
    member = self.s.scalar(select(WorkspaceMember).where(WorkspaceMember.user_id == user.id))
    ...
    return self._issue_tokens(user.id, member.workspace_id, member.role, new_family=True)
```

The challenge token must carry a distinct audience so it can never be presented
as an access token:

```python
# backend/app/modules/auth/security.py
MFA_AUDIENCE = "tendershield:mfa-challenge"
ACCESS_AUDIENCE = "tendershield:access"
```

`decode_access` must **verify** `aud == ACCESS_AUDIENCE` — otherwise the two
token types are interchangeable and the whole scheme is decorative.

### D.3 Replay guard

```python
# auth/models.py — User
mfa_last_used_slot: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
```

```python
def _consume_totp(self, user: User, code: str) -> bool:
    slot = int(time.time()) // 30
    for drift in (0, -1, 1):                       # ±30s clock tolerance
        candidate = slot + drift
        if mfa.verify_at(user.mfa_totp_secret, code, candidate):
            if user.mfa_last_used_slot is not None and candidate <= user.mfa_last_used_slot:
                return False                       # replay of an already-used code
            user.mfa_last_used_slot = candidate
            self.s.commit()
            return True
    return False
```

### D.4 Re-enrollment requires re-authentication

```python
def mfa_enroll(self, user_id, method: str, phone: str | None, current_password: str) -> dict:
    user = self.s.get(User, uuid.UUID(str(user_id)))
    if not user or not user.password_hash or not sec.verify_password(current_password, user.password_hash):
        raise AuthError("invalid_credentials")
    if user.mfa_totp_secret:
        # Changing an existing factor invalidates every session (R-002 §B.2).
        self._revoke_all_sessions(user.id)
    ...
```

Enrollment becomes two-step so a half-finished setup cannot lock the user out:
`POST /auth/mfa/enroll` returns the secret + `otpauth_uri` but stores it as
*pending*; `POST /auth/mfa/enroll/confirm` with a valid code promotes it and
returns ten single-use recovery codes (stored hashed, shown once).

### D.5 Recovery codes

```python
class MfaRecoveryCode(Base):
    __tablename__ = "mfa_recovery_codes"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Hash with the same argon2id helper used for passwords — these are password-grade
secrets, not tokens.

### D.6 `email` / `sms` MFA methods

`MfaEnrollBody` accepts `totp|email|sms` (`router.py:76`) but only TOTP has an
implementation, and the enroll response returns a TOTP secret regardless of the
method chosen. Until delivery exists (TS-035/TS-079), reject `email`/`sms` with
`501 mfa_method_unavailable` rather than silently issuing a TOTP secret.

---

## Behavior

- **B1** Reset tokens are delivered out-of-band only; the API returns them only
  when `TS_DEV_ECHO_TOKENS=true`, which production startup refuses.
- **B2** `forgot-password` returns an identical response for known and unknown
  emails, and issuing a new reset invalidates prior unused resets.
- **B3** A password reset revokes every refresh-token family for that user.
- **B4** Auth endpoints are rate limited per IP; repeated failures against one
  account trigger a capped, time-boxed backoff.
- **B5** When a user has MFA enrolled, password login yields only a 5-minute
  MFA-challenge token whose audience cannot be used as an access token.
- **B6** A TOTP code is single-use; replay within its window is rejected.
- **B7** Changing or re-enrolling a second factor requires the current password
  and revokes all sessions.
- **B8** Ten single-use recovery codes are issued at enrollment, stored hashed.

## Acceptance criteria

- **A1** `POST /auth/forgot-password` with default settings returns exactly
  `{"ok": true}`; no token field is present.
- **A2** `Settings(env="production", dev_echo_tokens=True)` raises at startup.
- **A3** Issuing a second reset marks the first `used_at`, and the first token
  then returns `400 invalid_reset_token`.
- **A4** After `reset-password`, a refresh token minted before the reset returns
  `401 invalid_refresh`.
- **A5** The 11th login attempt within 5 minutes from one IP returns `429` with
  a `Retry-After` header.
- **A6** 10 failed logins for one account return `423 account_locked`; the lock
  clears after the backoff window.
- **A7** A user with MFA enrolled receives `{"mfa_required": true, ...}` from
  `/auth/login` and **no** `access_token`.
- **A8** The MFA challenge token is rejected by `decode_access` (wrong audience).
- **A9** Replaying a TOTP code that already succeeded returns
  `401 invalid_mfa_code`.
- **A10** `mfa/enroll` without the current password returns `401`.
- **A11** A recovery code authenticates once and fails on reuse.

## Out of scope

- WebAuthn / passkeys (Phase 3).
- Phone OTP and Google OIDC login — TS-036, needs credentials.
- Distributed rate limiting — the in-memory limiter is correct for single-process
  deployments; the Redis backend arrives with R-016.

## Assumptions

- `assumption:` 15-minute access-token TTL is short enough that revoking refresh
  families is acceptable revocation. If TTL is raised, add a token-version claim
  checked per request.
