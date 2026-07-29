# TS-081 — Fix `accept_invitation` naive/aware datetime comparison + test

**Status:** done
**Requirement:** Doc §11.1
**Spec(s) updated:** none
**Module(s):** `auth`
**Severity / Gate:** P1 · Phase 1 (remaining)

## What this builds

A real bug fix: `Invitation.expires_at` read back from SQLite (tz-naive)
was compared directly against `datetime.now(UTC)` (tz-aware), which raises
`TypeError` under SQLite and silently misbehaves under drivers that
coerce — the exact naive/aware footgun this codebase has hit before
(`refresh.py`'s `_as_aware` helper exists for the same reason).

## Implementation

```python
# backend/app/modules/auth/service.py
def accept_invitation(self, user_id, token: str) -> dict:
    user_id = uuid.UUID(str(user_id))
    invitation = self.s.scalar(select(Invitation).where(Invitation.token == token))
    if not invitation:
        raise AuthError("invalid_invitation")
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        raise AuthError("invalid_invitation")
    ...
```

## Files touched

- `backend/app/modules/auth/service.py`

## Tests

- `backend/tests/modules/auth/test_service.py::test_accept_invitation_expired`
  (new — was the missing coverage that let this ship in the first place)

## Acceptance criteria

- [x] `accept_invitation` no longer raises `TypeError` comparing a naive
      `expires_at` against an aware `now()`.
- [x] An expired invitation is correctly rejected regardless of the DB
      driver's datetime tz-awareness.

## Commit

Predates commit-granular history (PR #10 bulk import).
