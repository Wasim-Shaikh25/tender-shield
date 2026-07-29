# TS-035 — SES/Resend + MSG91 send adapters behind the notifications interface

**Status:** todo (needs creds)
**Requirement:** Doc §4, §11.6
**Spec(s) updated:** `specs/modules/notifications.md` (to be updated when built)
**Module(s):** `notifications`
**Severity / Gate:** P2 · Phase 1 MVP

## What this builds

Real email (SES or Resend) and SMS (MSG91) senders implementing the
`Sender` protocol TS-027 already defined — swapping `ConsoleSender` for a
production sender in deployments that have the provider credentials
configured.

## Implementation (reference plan — not yet built; blocked on provider creds)

```python
# backend/app/modules/notifications/sender.py (existing Protocol to implement against)
class Sender(Protocol): ...
```

- `SesSender` / `ResendSender` implementing `Sender.send(Message) -> None`
  over the respective HTTP API.
- `Msg91Sender` for SMS, same interface.
- Selection via `TS_NOTIFICATIONS_PROVIDER` env var; absence of credentials
  falls back to `ConsoleSender` (soft-dependency degrade, not a crash —
  CLAUDE.md §2).

## Files touched (planned)

- `backend/app/modules/notifications/sender.py`, `config.py`

## Tests (planned)

- Adapter unit tests with a mocked HTTP client (no real send in CI).

## Acceptance criteria

- [ ] A configured SES/Resend/MSG91 sender delivers a real message.
- [ ] Missing credentials degrades to `ConsoleSender`, never a startup crash.

## Commit

Not yet implemented — blocked on provider credentials.
