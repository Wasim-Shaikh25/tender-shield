# Notifications — Spec

**Status:** implemented (core digest + `Sender` protocol + daily deadline alert scheduler +
change-notice countdown via `change.process_notice_alerts`). Real adapters and the scheduler are
wired as an APScheduler job scanning all workspaces for deadlines in the `7`, `3`, `1`, `0` day
buckets and emailing members. SES/Resend/MSG91 adapters are credential-gated.
**Requirement refs:** Doc §11.6, §11.7, Research Doc §4.F, `PRODUCTION_READINESS_AUDIT.md` F15/F07
**Task refs:** TS-027, TS-035, TS-043, TS-079, TS-091, TS-111, TS-252

## Purpose

Deadline-digest notification path: decide which upcoming deadlines warrant an alert, format the message, and hand it to a pluggable sender. The core logic is pure and dependency-free; the `Sender` protocol is backed by `ConsoleSender` in dev/test and by SES/Resend/MSG91 adapters when credentials are configured.

## Public interface

- **Capabilities published:**
  - `notifications.sender` → a `Sender` instance (`ConsoleSender` by default;
    `SESSender`, `ResendSender`, or `MSG91Sender` when configured).
- **Capabilities consumed (soft):**
  - `ingestion.service_factory` (to fetch deadlines + opportunity title).
  - `auth.workspace_factory` (to enumerate workspaces and members).
  - `change.process_notice_alerts` (notice-deadline countdown for confirmed change events).
- **Events emitted:** none.
- **Events consumed:** none.
- **API routes:** none at this phase. The digest is driven by a periodic job
  (APScheduler/Redis); admin tooling may call the scheduler tick directly.

## Data owned

- `notification_preferences` — one row per user (`user_id` PK) controlling
  `email_deadlines` (default `true`) and `sms_deadlines` (default `false`), plus
  optional `quiet_hours_start` / `quiet_hours_end`.
- `deadline_alert_log` — workspace-scoped record of `(user_id, deadline_id, alert_day)`
  alerts already sent. Unique on `(user_id, deadline_id, alert_day)`. RLS-enforced.

Change-notice alerts are deduped in the `change` module's `change_notice_alert_log` table
(TS-252); this module invokes `change.process_notice_alerts` from the daily scheduler tick.

## Behavior

- **B1 — Alert windows:** `_alert_day` buckets a deadline into `7`, `3`, `1`, or
  `0` days before `due_at`. Past deadlines and deadlines more than 7 days out are
  ignored.
- **B2 — Deduplication:** The scheduler only sends one alert per `(user, deadline,
  bucket)` by checking `deadline_alert_log`. After a successful send a row is
  inserted and committed.
- **B3 — User preferences:** Alerts are only sent when the user's
  `NotificationPreference` allows the channel (`email_deadlines` for email). A missing
  preference row defaults to email enabled.
- **B4 — Message formatting:** `format_digest` builds a plain-text summary with
  one line per alert, ordered by urgency (`TODAY` for 0 days).
- **B5 — Sender protocol:** `Sender.send(message: Message) -> bool` is channel
  agnostic (`email`, `sms`, `whatsapp`).
- **B6 — Graceful degradation:** If no sender is configured, notifications are
  silently skipped. If `ingestion` or `auth` is disabled, the scheduler tick returns.
- **B7 — Adapters:** `SESSender` sends via AWS SES when `TS_SES_*` credentials
  are configured; `ResendSender` sends email via Resend when `TS_RESEND_API_KEY`
  is configured; `MSG91Sender` sends SMS via MSG91 when `TS_MSG91_*` is
  configured; otherwise `ConsoleSender` is used and logs a warning in production.
- **B8 — Scheduler integration:** The `notifications` module registers a daily job on
  `core.scheduler` that scans all workspaces for unconfirmed deadlines in the
  configured buckets, checks per-user preferences and deduplication, and emails
  workspace members. When `change` is enabled, the same tick also calls
  `change.process_notice_alerts` for confirmed change events with computed notice deadlines.
  A Redis lock prevents duplicate scheduler runs across
  instances. Without Redis/APScheduler it degrades to a no-op.
- **B9 — Org isolation:** `deadline_alert_log` is workspace-scoped and governed by
  PostgreSQL RLS.

## Acceptance criteria

- A1: A deadline 3 days away is bucketed into the `3` alert window.
- A2: A deadline 5 days away is bucketed into the `7` alert window.
- A3: A deadline 10 days away produces no alert bucket.
- A4: `ConsoleSender` records the message and reports success.
- A5: `DeadlineAlertLog` prevents a second send for the same `(user, deadline, bucket)`.
- A6: `NotificationPreference.email_deadlines=False` suppresses email alerts.
- A7: `WorkspaceAdmin.list_members` returns `user_id` + `email` so the scheduler can
  look up preferences.

## Out of scope

- WhatsApp/Telegram adapters (P3).
- Push/mobile native notifications (P3).
