# TS-093 — Revoke all refresh-token families on password reset

**Status:** done
**Requirement:** [R-002 §B](../../specs/requirements/R-002-auth-hardening.md)
**Spec(s) updated:** `specs/modules/auth.md`
**Module(s):** `auth`
**Severity / Gate:** P1 · Gate 1

## What this builds

Closes the gap where an attacker holding a hijacked session keeps it even
after the victim resets their password — which defeats the main reason
people reset passwords in the first place.

## Current (the defect)

```python
# backend/app/modules/auth/service.py:503 (before this task)
def reset_password(self, token: str, new_password: str) -> dict:
    ...
    user.password_hash = sec.hash_password(new_password)
    row.used_at = datetime.now(UTC)
    self.s.commit()
    return {"ok": True}
    # refresh-token families untouched — attacker's session survives
```

## Implementation

```python
# backend/app/modules/auth/service.py
def reset_password(self, token: str, new_password: str) -> dict:
    ...
    user.password_hash = sec.hash_password(new_password)
    row.used_at = datetime.now(UTC)
    self._revoke_all_sessions(user.id)      # every family, every device
    self.s.commit()
    return {"ok": True}

def _revoke_all_sessions(self, user_id) -> None:
    """Access tokens are stateless (15-min TTL, TS-011), so revocation is
    eventual for those; refresh families die immediately, capping an
    attacker's remaining window at one access-token TTL."""
    self.s.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == uuid.UUID(str(user_id)), RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
```

Applied on: successful `reset_password`, MFA re-enrollment (TS-101), and
`POST /auth/logout-all`. Also adds session-management endpoints
(`GET /api/auth/sessions`, `DELETE /api/auth/sessions/{family}`,
`POST /api/auth/logout-all`) needing `user_agent`/`ip` columns on
`refresh_tokens`, plus a pruning job for expired rows (never deleted
before, unbounded growth).

## Files touched

- `backend/app/modules/auth/{service,router,models}.py`
- `backend/migrations/versions/` (new `user_agent`/`ip` columns)

## Tests

- `backend/tests/modules/auth/test_service.py::test_reset_password_revokes_sessions`

## Acceptance criteria (R-002 §B, A4)

- [x] Every refresh-token family for the user is revoked on password reset.
- [x] Session-management endpoints (`GET /sessions`, `DELETE /sessions/{id}`,
      `POST /logout-all`) work against real refresh-token rows.

## Commit

Predates commit-granular history (PR #10 bulk import).
