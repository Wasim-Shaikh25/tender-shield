# Notifications — Spec

**Status:** implemented (core digest + `Sender` protocol); real adapters and
periodic scheduler are wired as a daily APScheduler/Celery job scanning all workspaces
for 7-day deadlines and emailing members; SES/MSG91 adapters are credential-gated.
**Requirement refs:** Doc §11.6, §11.7, `PRODUCTION_READINESS_AUDIT.md` F15/F07
**Task refs:** TS-027, TS-035, TS-043, TS-079, TS-091

## Purpose

Deadline-digest notification path: decide which upcoming deadlines warrant an
alert, format the message, and hand it to a pluggable sender. The core logic is
pure and dependency-free; the `Sender` protocol is backed by `ConsoleSender` in
dev/test and by SES/MSG91 adapters when credentials are configured.

## Public interface

- **Capabilities published:**
  - `notifications.sender` → a `Sender` instance (`ConsoleSender` by default;
    `SESSender` or `MSG91Sender` when configured).
  - `notifications.scheduler` → `NotificationScheduler` stub that scans deadlines
    and hands alerts to the sender.
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
- **B5 — Adapters:** `SESSender` sends via AWS SES when `TS_SES_*` credentials
  are configured; `MSG91Sender` sends SMS via MSG91 when `TS_MSG91_*` is
  configured; otherwise `ConsoleSender` is used and logs a warning in production.
- **B6 — Scheduler integration:** The `notifications` module registers a daily job on
  `core.scheduler` that scans all workspaces for unconfirmed deadlines within 7 days
  and emails workspace members. Without Redis/APScheduler it degrades to a no-op.

## Acceptance criteria

- A1: A deadline 3 days away is included in `deadlines_to_alert`.
- A2: A deadline 5 days away is NOT included.
- A3: `ConsoleSender` records the message and reports success.
- A4: `SESSender` with mocked boto3 `send_email` is called when configured.
- A5: `NotificationScheduler.tick()` with `ConsoleSender` produces one message
  per upcoming deadline.

## Out of scope

- Celery beat / production cron (P2, needs Redis).
- Per-user subscription preferences (P2).
- WhatsApp/Telegram adapters (P3).
