# TS-085 — Gate the dev token echo behind a dev-only setting

**Status:** done
**Requirement:** [R-002 §A](../../specs/requirements/R-002-auth-hardening.md)
**Spec(s) updated:** `specs/modules/auth.md`
**Module(s):** `auth`, `core`
**Severity / Gate:** P0 · Gate 1

## What this builds

Closes an unauthenticated account-takeover: `forgot_password` returned the
raw reset token in its HTTP response body — to anyone who knew a user's
email, no authentication required. `create_invitation` had the same shape.

## Current (the defect)

```python
# backend/app/modules/auth/service.py:491 (before this task)
def forgot_password(self, email: str) -> dict:
    ...
    self.s.add(PasswordReset(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    self.s.commit()
    # TODO: wire email delivery; return token for dev/test until delivery exists
    return {"ok": True, "token": raw}          # returned to an UNAUTHENTICATED caller
```

## Implementation

```python
# backend/app/core/config.py
env: str = "dev"
dev_echo_tokens: bool = False   # DEV ONLY — see docstring in real file

def model_post_init(self, __context) -> None:
    if self.env == "production" and self.dev_echo_tokens:
        raise ValueError(
            "TS_DEV_ECHO_TOKENS must be false when TS_ENV=production "
            "(it returns password-reset tokens to unauthenticated callers)"
        )
```

```python
# backend/app/modules/auth/service.py
def forgot_password(self, email: str) -> dict:
    ...
    if not user:
        return {"ok": True}            # constant response — no enumeration
    ...
    self._send_reset_email(user.email, raw)
    return {"ok": True, "token": raw} if self._echo_tokens else {"ok": True}

def _send_reset_email(self, email: str, raw_token: str) -> None:
    if self._notifier is None:
        logger.warning("password reset requested but no notifications sender is available")
        return
    self._notifier.send(Message(channel="email", to=email, ...))
```

Delivery goes through the `notifications.sender` registry capability so
`auth` never imports `notifications` (CLAUDE.md §2). Also required: any
outstanding unused reset is invalidated when a new one is issued (replay
prevention), and the frontend `/forgot-password` page stops displaying the
token unconditionally.

## Files touched

- `backend/app/core/config.py`
- `backend/app/modules/auth/{service,router}.py`
- `backend/app/modules/notifications/module.py` (publish `notifications.sender`)
- `.env.example`, `frontend/app/forgot-password/page.tsx`

## Tests

- `backend/tests/modules/auth/test_service.py::test_forgot_password_no_echo_in_prod`
- `backend/tests/test_core_config.py::test_dev_echo_tokens_refused_in_production`

## Acceptance criteria (R-002 §A, A1–A3)

- [x] `TS_ENV=production` + `TS_DEV_ECHO_TOKENS=true` refuses to start.
- [x] A non-existent email and an existing email both get the identical
      `{"ok": true}` response (no enumeration).
- [x] An outstanding reset token is invalidated when a new one is requested.

## Commit

Predates commit-granular history (PR #10 bulk import).
