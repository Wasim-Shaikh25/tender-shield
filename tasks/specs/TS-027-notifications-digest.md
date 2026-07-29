# TS-027 — Deadline-digest notifications: pluggable sender + dev console sender

**Status:** done
**Requirement:** Doc §11.6, §11.7
**Spec(s) updated:** `specs/modules/notifications.md`
**Module(s):** `notifications`
**Severity / Gate:** P1 · Phase 1 MVP

## What this builds

A `notifications` module that computes which deadlines are due soon and
formats a digest, behind a pluggable `Sender` interface so a real
email/SMS provider (TS-035) can be swapped in later without touching the
digest logic.

## Implementation

```python
# backend/app/modules/notifications/digest.py
def due_in_days(due_at: datetime, now: datetime) -> int: ...
def deadlines_to_alert(deadlines: list[dict], now: datetime) -> list[dict]: ...
def format_digest(opportunity_title: str, alerts: list[dict]) -> str: ...
```

```python
# backend/app/modules/notifications/sender.py
class Message: ...
class Sender(Protocol): ...
class ConsoleSender:
    """Dev-mode sender: logs the message instead of sending it — lets the
    digest pipeline run end-to-end with zero external credentials."""
```

## Files touched

- `backend/app/modules/notifications/{digest,sender,module}.py`

## Tests

- `backend/tests/modules/notifications/test_digest.py`

## Acceptance criteria

- [x] `deadlines_to_alert` correctly windows deadlines by days-remaining.
- [x] `Sender` is swappable without changing digest logic (ConsoleSender in
      dev, a real provider in TS-035).

## Commit

Predates commit-granular history (PR #10 bulk import).
