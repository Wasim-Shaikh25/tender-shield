# R-020 — Deadline alerting that is actually delivered

**Status:** draft
**Severity:** P0 — the product's primary promise (never miss a deadline trap) is
unrealised; the digest logic is written and has zero callers
**Requirement refs:** Doc §11.6, §11.7; product overview §Purpose
**Task refs:** TS-113 · **Depends on:** R-016/TS-105 (job scheduler),
R-015/TS-099 (email delivery adapter)
**Gap refs:** `docs/PRODUCT_DISCOVERY_GAPS.md` §G-04
**Specs to update:** `specs/modules/notifications.md`, `specs/frontend.md`

## Purpose

`backend/app/modules/notifications/digest.py` implements the alert thresholds,
the selection logic and the message formatting exactly as Doc §11.6/§11.7
specifies:

```python
ALERT_DAYS = (7, 3, 1, 0)
def deadlines_to_alert(deadlines, now) -> list[dict]
def format_digest(opportunity_title, alerts) -> str
```

It has **zero callers anywhere in the application**. The notifications module
registers `router=None` and a `ConsoleSender` that only writes to the log.

So the product will tell you about a deadline trap only if you happen to open it
that day. For a tool whose entire premise is that missing a deadline is the
failure it prevents, this is the gap that matters most after upload (R-017).

## Target

### B.1 One scheduled evaluation, one digest per user per day

A daily job walks every live opportunity's **confirmed** deadlines, groups by
recipient, and sends **one digest per user per day** — not one message per
deadline. A commercial head with eight live tenders must not receive eight emails.

### B.2 Only confirmed deadlines alert

Extracted deadlines carry a citation and must be human-confirmed before they are
relied on (`Deadline.confirmed`, the product's own provenance invariant). An
unconfirmed extraction must never trigger an alert — alerting on an
unverified date is precisely the failure mode the confirmation step exists to
prevent.

### B.3 Send-once semantics

A `notification_log` records what was sent to whom for which threshold. A retried
or double-scheduled job must not double-send — the same idempotent-insert idiom
used for `webhook_events` and `coupon_redemptions` (unique constraint +
`IntegrityError` caught, not check-then-act).

### B.4 Preferences and quiet hours

Per-user opt-in/out and a delivery window. Opt-out takes effect immediately.

### B.5 In-app surface

The same records drive an in-app notification list, so the product is useful to
someone who has muted email.

### B.6 Terminal-state opportunities stop alerting

An opportunity that is `won`, `lost`, `withdrawn` or `no_bid` (R-018) or archived
(R-019) generates no alerts.

## Behavior

- **B1** A confirmed deadline at 7/3/1/0 days generates exactly one alert per
  recipient per day.
- **B2** Unconfirmed deadlines never alert.
- **B3** A retried job never double-sends.
- **B4** Opt-out is immediate.
- **B5** Closed or archived opportunities stop alerting.
- **B6** Delivery failures are recorded and retried, not silently dropped.

## Acceptance criteria

- **A1** Three deadlines across two opportunities at the 3-day threshold produce
  one digest listing all three, not three messages.
- **A2** An unconfirmed deadline at 1 day produces no alert; confirming it makes
  the next run alert.
- **A3** Running the job twice for the same day sends once (asserted against the
  send log, not just observed behavior).
- **A4** An opted-out user receives nothing.
- **A5** Archiving an opportunity stops its alerts on the next run.
- **A6** A send failure is recorded with its cause and retried on the next run.

## Out of scope

- **WhatsApp delivery.** The product overview lists WhatsApp alert UI as P2.
  India-first SMB distribution arguably makes it more important than email, so
  this is a **product decision**, not a settled deferral — see Questions.
- Digest scheduling per-user timezone beyond a single configured default.
- Escalation (alerting a manager when the assignee does not act) — requires
  assignment, which does not exist (see R-023 §G-15).

## Questions for the product owner

1. **Is WhatsApp required at launch** for the India SMB segment, or is email
   sufficient for v1?
2. **Who is alerted by default** — every workspace member, or only the person
   the opportunity is assigned to? **There is no assignment concept in the
   product today.** If the answer is "assignee", assignment must be built first
   and this task grows.
3. What is the default quiet-hours window, and is it per-user or per-workspace?

## Assumptions

- `assumption:` every workspace member receives alerts for every live
  opportunity in v1, because assignment does not exist. This is acceptable at
  small team sizes and becomes noise quickly — it is the main reason Question 2
  needs an early answer.
- `assumption:` email is the launch channel, given `notifications.sender` already
  abstracts delivery and R-015/TS-099 is already building a real adapter.
