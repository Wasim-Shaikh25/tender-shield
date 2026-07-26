# Notifications — Spec

**Status:** implemented
**Requirement refs:** Doc §11.6, §11.7
**Task refs:** TS-027, TS-035

## Purpose

Deadline-digest notification path: decide which upcoming deadlines warrant an
alert, format the message, and hand it to a pluggable sender. The core logic is
pure and dependency-free; the `Sender` protocol is backed by `ConsoleSender` in
dev/test and by SES/Resend/MSG91 adapters in production (TS-035, needs
credentials).

## Public interface

- **Capabilities published:**
  - `notifications.sender` → a `Sender` instance (currently `ConsoleSender`).
- **Capabilities consumed (soft):**
  - `ingestion.service_factory` (to fetch deadlines + opportunity title).
- **Events emitted:** none.
- **Events consumed:** none.
- **API routes:** none at this phase. The digest is intended to be driven by a
  periodic job (Celery/Redis, TS-034) or called directly by admin tooling.

## Data owned

None. `ConsoleSender.outbox` is an in-memory store used for testing.

## Behavior

- **B1 — Alert windows:** `deadlines_to_alert` checks deadlines at `7`, `3`, `1`,
  and `0` days before `due_at` and returns those whose day-count is in the set
  and not already past.
- **B2 — Message formatting:** `format_digest` builds a plain-text summary with
  one line per alert, ordered by urgency (`TODAY` for 0 days).
- **B3 — Sender protocol:** `Sender.send(message: Message) -> bool` is channel
  agnostic (`email`, `sms`, `whatsapp`).
- **B4 — Graceful degradation:** If no sender is configured, notifications are
  silently skipped. If `ingestion` is disabled, there are no deadlines to alert.

## Acceptance criteria

- A1: A deadline 3 days away is included in `deadlines_to_alert`.
- A2: A deadline 5 days away is NOT included.
- A3: `ConsoleSender` records the message and reports success.

## Out of scope

- Periodic scheduler / Celery beat (TS-034, needs Redis).
- Real email/SMS adapters (TS-035, needs credentials).
- Per-user subscription preferences (P2).
