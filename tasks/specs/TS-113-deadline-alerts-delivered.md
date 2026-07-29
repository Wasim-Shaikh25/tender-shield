# TS-113 — Deadline alerts actually delivered

**Status:** todo
**Requirement:** [R-020](../../specs/requirements/R-020-deadline-alerting.md)
**Spec(s) updated:** `specs/modules/notifications.md` (to be updated when built)
**Module(s):** `notifications`, frontend
**Severity / Gate:** P0 · Gate 5

## What this builds

`notifications/digest.py` (TS-027) computes which deadlines are due soon
and formats a digest — but has zero callers. Nothing schedules it, so the
product's core "<3-minute deadline wall" promise never actually reaches a
user outside the app. Depends on TS-105's job scheduler.

## Implementation (reference plan — not yet built)

One scheduled evaluation, one digest per user per day — a daily job walks
every live opportunity's **confirmed** deadlines (TS-015), groups by
recipient, and sends one digest, not one message per deadline (a
commercial head with eight live tenders must not receive eight emails).

Only confirmed deadlines alert: an unconfirmed extraction must never
trigger an alert — alerting on an unverified date is precisely the failure
mode the confirm-chip step (TS-015) exists to prevent.

Send-once semantics via the same idempotent-insert idiom used for
`webhook_events` (TS-097) and `coupon_redemptions` (TS-090) — a
`notification_log` row with a unique constraint, `IntegrityError` caught
rather than check-then-act, so a retried or double-scheduled job can't
double-send.

Per-user preferences (opt-in/out, delivery window) with opt-out taking
effect immediately; the same records drive an in-app notification list, so
the product is useful to someone who has muted email. Terminal-state
(TS-111) or archived (TS-112) opportunities generate no alerts.

## Files touched (planned)

- `backend/app/modules/notifications/{digest,scheduler}.py`
- new `notification_log` reuse (shared with TS-099) or dedicated table
- depends on TS-105 (job scheduler)

## Tests (planned)

- `backend/tests/modules/notifications/test_scheduler.py::test_one_digest_per_user_per_day`,
  `test_unconfirmed_deadline_never_alerts`, `test_double_schedule_no_double_send`

## Acceptance criteria (R-020, A1–A6)

- [ ] A confirmed deadline at 7/3/1/0 days generates exactly one alert per
      threshold, batched into one daily digest per user.
- [ ] An unconfirmed deadline never triggers an alert.
- [ ] A double-scheduled run does not double-send.
- [ ] A terminal-state or archived opportunity generates no further alerts.

## Commit

Not yet implemented.
