# TS-099 — Email verification, delivery adapters, disposable-email blocklist, canonical-email abuse counting

**Status:** todo
**Requirement:** [R-015](../../specs/requirements/R-015-email-verification.md)
**Spec(s) updated:** `specs/modules/notifications.md`, `specs/modules/auth.md`
  (to be updated when built)
**Module(s):** `auth`, `notifications`
**Severity / Gate:** P1 · Gate 3

## What this builds

Real email delivery (`notifications.Sender` has no real adapter yet, only
`ConsoleSender`), email verification gating the free review specifically
(not signup or paid review), and free-tier anti-abuse (disposable-email
blocklist, canonical-email abuse counting) that Doc §706 calls for but
doesn't exist.

## Implementation (reference plan — not yet built)

```python
# backend/app/modules/notifications/adapters/smtp.py
class SmtpSender:
    """Provider-agnostic SMTP — works with SES, Resend, Postmark, local
    MailHog, so a provider decision (TS-035) is not a code change."""
```

```python
# backend/app/modules/notifications/module.py — fail loudly, not silently
def setup(ctx):
    if s.smtp_host:
        sender = SmtpSender(...)
    else:
        sender = ConsoleSender()
        if s.env == "production":
            raise RuntimeError("TS_SMTP_HOST is required when TS_ENV=production")
    ctx.registry.provide("notifications.sender", sender)
```

Templates are plain-text-first (`TEMPLATES` dict: verify_email,
password_reset, invitation, deadline_digest, payment_failed,
invoice_issued) — "contractors read email on phones over patchy links, and
an HTML-only deadline alert that fails to render is a missed submission."
`NotificationLog` records every send attempt with a *hashed* recipient
(never the raw address — avoids duplicating PII into a second erasure
target) plus a suppression list for hard bounces.

```python
# email verification gates ONLY the free review, not signup/login/paid review
if grant.kind == "free_first_review" and not user.email_verified:
    raise HTTPException(403, detail={"code": "email_verification_required", "email": user.email})
```

Blocking only at the free review is deliberate — the user has already
uploaded a tender and seen the deadline wall by then, so they have a reason
to verify; blocking at signup loses people who never come back. Changing
an email verifies the new address before it takes effect and notifies the
old one (prevents silent account takeover via a stolen session).

```python
# backend/app/modules/auth/email_policy.py
"""A static blocklist is a speed bump, not a wall — raise the cost of
casual abuse above paying, not defeat a determined attacker."""

def check_signup_email(email: str) -> None:
    if domain in DISPOSABLE_DOMAINS:
        raise AuthError("disposable_email_not_allowed")

def canonical_email(email: str) -> str:
    """Normalizes provider aliasing (alice+1@gmail.com, a.l.i.c.e@gmail.com)
    for ABUSE COUNTING ONLY — never for login lookup, which would break
    users who legitimately signed up with a dotted Gmail address."""
```

One free review per canonical email + (once TS-036 lands) per verified
phone via a unique index on `users.phone WHERE phone_verified`. Also caps
free-review signups per IP/24h and per email domain as additional signals
— individually weak, together raise the cost of a second free review above
the ₹7,500 paygo price, which is the actual goal.

## Files touched (planned)

- `backend/app/modules/notifications/{adapters/smtp,templates,module}.py`
- `backend/app/modules/auth/{email_policy,service,models}.py`
- new `email_verifications`, `notification_log` tables + migrations

## Tests (planned)

- `backend/tests/modules/auth/test_email_policy.py::test_canonical_email_not_used_for_login`
- `backend/tests/modules/notifications/test_smtp_sender.py`

## Acceptance criteria (R-015, A1–A11)

- [ ] A production boot with no SMTP configured fails at startup, not at
      the first password-reset attempt.
- [ ] The free review is blocked for an unverified email; signup, login,
      and paid review are not.
- [ ] `canonical_email` is never used for login lookup, only abuse
      counting.

## Commit

Not yet implemented.
