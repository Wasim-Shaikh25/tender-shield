# TS-082 — Forgot-password and reset-password flow

**Status:** done
**Requirement:** Doc §5
**Spec(s) updated:** `specs/modules/auth.md`
**Module(s):** `auth`
**Severity / Gate:** P1 · Phase 1 (remaining)

## What this builds

The password-recovery flow: request a reset token via email (console-logged
in dev mode, same honest-degradation pattern as MFA delivery), then reset
the password with that token.

## Implementation

```python
# backend/app/modules/auth/router.py
@router.post("/forgot-password")
def forgot_password(...): ...

@router.post("/reset-password")
def reset_password(...): ...
```

`AuthService.forgot_password` generates a single-use, expiring token; in
dev mode the response echoes the token directly (`self._echo_tokens`) so
the flow is testable without a real email provider — never echoed in
production config.

## Files touched

- `backend/app/modules/auth/{router,service,models}.py`

## Tests

- `backend/tests/modules/auth/test_service.py::test_forgot_reset_password`

## Acceptance criteria

- [x] A reset token is single-use and expires.
- [x] `_echo_tokens` (dev-mode token echo) is off in production
      configuration.

## Commit

Predates commit-granular history (PR #10 bulk import).
