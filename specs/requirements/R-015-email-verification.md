# R-015 — Email verification, delivery adapters, free-tier anti-abuse

**Status:** draft
**Severity:** P1 — free-tier abuse is open; no transactional email exists
**Requirement refs:** Doc §5, §11.6, §706
**Task refs:** TS-099 (verification + anti-abuse), TS-035 (delivery adapters)
**Task files:** code-level detail (current-vs-target snippets, file:line, files touched, tests) now lives per-task, split out by TS-126's restructure: [TS-099](../../tasks/specs/TS-099-email-verification-anti-abuse.md). This document stays the business/behavior-level record (purpose, target behavior, acceptance criteria).

**Gap refs:** `docs/GAP_ANALYSIS.md` §3.1, §2.9
**Specs to update:** `specs/modules/auth.md`, `specs/modules/notifications.md`

## Purpose

`signup` creates a user with `email_verified=False` and never sends anything;
the flag is only ever set to `True` by the Apple path (`auth/service.py:184`).
Nothing gates on it. Three consequences:

1. **Free-tier abuse is one throwaway email away** — unlimited free reviews.
   Doc §706 explicitly requires "one free org per verified phone; disposable-email
   blocklist".
2. **No transactional email exists at all**, so password reset (R-002 §A.2),
   invitations (R-013 §1), invoices (R-007 §B.4) and deadline digests all have no
   delivery path.
3. **Deadline digests would bounce** — and the digest is described in the build
   doc as the most safety-critical path in the product (§11.6).

## A. Delivery adapters

The interface already exists and is well shaped:

```python
# backend/app/modules/notifications/sender.py:20
class Sender(Protocol):
    def send(self, message: Message) -> bool: ...
```

`ConsoleSender` is the dev backend. What is missing is any real adapter, a
templating layer, and a delivery ledger.

```python
# backend/app/modules/notifications/adapters/smtp.py

class SmtpSender:
    """Provider-agnostic SMTP. Works with SES, Resend, Postmark and a local
    MailHog, so a provider decision is not a code change (TS-035)."""

    def __init__(self, host, port, username, password, from_addr, *, use_tls=True):
        ...

    def send(self, message: Message) -> bool:
        if message.channel != "email":
            return False
        ...
```

Selection at startup, degrading loudly rather than silently:

```python
# backend/app/modules/notifications/module.py

def setup(ctx: AppContext) -> None:
    s = ctx.settings
    if s.smtp_host:
        sender = SmtpSender(...)
    else:
        sender = ConsoleSender()
        if s.env == "production":
            # A production deployment with no mail provider cannot deliver
            # password resets or deadline alerts. Fail at boot, not at 2am.
            raise RuntimeError("TS_SMTP_HOST is required when TS_ENV=production")
        logger.warning("notifications: no SMTP configured — using ConsoleSender (dev only)")
    ctx.registry.provide("notifications.sender", sender)
```

`notifications` currently publishes only the digest capability — check
`module.py` and add `notifications.sender`, which R-002 §A.2 depends on.

### A.1 Templates

```python
# backend/app/modules/notifications/templates.py

@dataclass(frozen=True)
class Template:
    subject: str
    text: str          # plain text is the source of truth
    html: str | None = None


TEMPLATES: dict[str, Template] = {
    "verify_email": Template(
        subject="Verify your email for TenderShield",
        text="Confirm your address to activate your workspace:\n\n{url}\n\nThis link expires in 24 hours.",
    ),
    "password_reset": Template(
        subject="Reset your TenderShield password",
        text="Reset your password:\n\n{url}\n\nExpires in 15 minutes. If you didn't ask for this, ignore this email.",
    ),
    "invitation": Template(
        subject="{inviter} invited you to {workspace} on TenderShield",
        text="{inviter} has invited you to join {workspace}.\n\n{url}\n\nThis invitation expires in 7 days.",
    ),
    "deadline_digest": Template(
        subject="{count} tender deadline(s) this week",
        text="{lines}\n\nOpen your deadline wall: {url}",
    ),
    "payment_failed": Template(
        subject="We couldn't process your TenderShield payment",
        text="Your payment failed. Your workspace keeps full access until {grace_until}.\n\nUpdate payment: {url}",
    ),
    "invoice_issued": Template(
        subject="Invoice {number} from TenderShield",
        text="Your invoice for {amount} is attached.\n\n{url}",
    ),
}
```

Plain text is authoritative. Every one of these must be readable and actionable
without HTML — contractors read email on phones over patchy links, and an
HTML-only deadline alert that fails to render is a missed submission.

### A.2 Delivery ledger

```python
class NotificationLog(Base, WorkspaceScopedMixin):
    """Every send attempt. Without this, "did the reset email go out?" is
    unanswerable, which makes support impossible."""

    _tablename_ = "notification_log"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    template: Mapped[str] = mapped_column(String, nullable=False)
    to_hash: Mapped[str] = mapped_column(String, nullable=False)   # hashed: no PII duplication
    status: Mapped[str] = mapped_column(String, nullable=False)    # queued|sent|failed|bounced
    provider_message_id: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Store a hash of the recipient, not the address — the address is already on the
user row, and duplicating PII into a log table creates a second erasure target.

Suppression list for hard bounces and complaints: never send to a hard-bounced
address again, or the sending domain's reputation degrades and *deadline alerts*
start landing in spam.

## B. Email verification

```python
class EmailVerification(Base):
    __tablename__ = "email_verifications"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"),
                                               nullable=False, index=True)
    email: Mapped[str] = mapped_column(String, nullable=False)   # supports email *change*
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

```
POST /api/auth/verify-email/send      resend (rate limited, 3/hour)
POST /api/auth/verify-email/confirm   {token} → marks verified
```

### B.1 What verification gates — and what it must not

The decision that matters. Gating too much destroys activation; gating too little
leaves the abuse open.

| Action | Requires verified email | Why |
|---|---|---|
| Sign in | no | Locking out a mistyped signup is worse than the abuse |
| Create opportunity, upload | no | Let them reach the value first |
| **Run the free review** | **yes** | The thing being abused |
| Paid review | no | A card payment is a stronger identity signal than an email |
| Invite members | yes | Prevents using invitations as a spam relay |
| Receive digests | yes | Unverified addresses bounce |

Blocking only at the free review is deliberate: the user has already uploaded a
tender and seen the deadline wall, so they have a reason to verify. Blocking at
signup loses people who never come back.

```python
# in the meter() path (R-004 §A.2), for free grants only
if grant.kind == "free_first_review" and not user.email_verified:
    raise HTTPException(403, detail={
        "code": "email_verification_required",
        "email": user.email,
    })
```

### B.2 Email change

Changing an email must verify the **new** address before it takes effect, and
notify the **old** one — an attacker with a session should not be able to
silently take over the account by swapping the address.

## C. Free-tier anti-abuse

Doc §706 requires "one free org per verified phone; disposable-email blocklist".
Neither exists.

### C.1 Disposable-email blocklist

```python
# backend/app/modules/auth/email_policy.py

"""Signup email policy. A static blocklist is a speed bump, not a wall — the
goal is to make casual abuse (a second free review) more effort than paying,
not to defeat a determined attacker (R-015 §C.1)."""

DISPOSABLE_DOMAINS: frozenset[str] = frozenset(_load("disposable_domains.txt"))


def check_signup_email(email: str) -> None:
    local, _, domain = email.strip().lower().rpartition("@")
    if not domain or "." not in domain:
        raise AuthError("invalid_email")
    if domain in DISPOSABLE_DOMAINS:
        raise AuthError("disposable_email_not_allowed")


def canonical_email(email: str) -> str:
    """Normalise provider-specific aliasing so alice+1@gmail.com and
    a.l.i.c.e@gmail.com collapse to one identity for abuse counting only.

    NEVER used for login lookup — users legitimately expect their address to
    work exactly as they typed it.
    """
    local, _, domain = email.strip().lower().rpartition("@")
    local = local.split("+", 1)[0]
    if domain in {"gmail.com", "googlemail.com"}:
        local = local.replace(".", "")
    return f"{local}@{domain}"
```

Store `canonical_email` on the user (indexed, non-unique) and count free reviews
per canonical address. The comment is important: canonicalisation is for abuse
accounting only. Using it for login would break legitimate users who signed up
with a dotted Gmail address.

### C.2 Phone verification

`User.phone` already exists (`auth/models.py:23`) and is unused. Phone OTP needs
MSG91 (TS-036, needs credentials), so build the gate now and enable it when the
adapter lands:

```python
# free review requires a verified phone when phone verification is enabled
if settings.require_phone_for_free_review and not user.phone_verified:
    raise HTTPException(403, detail={"code": "phone_verification_required"})
```

One free review per verified phone, enforced by a unique index on
`users.phone` where `phone_verified`.

### C.3 Signal-based limits

Beyond email and phone: cap free-review signups per IP/24h and per email domain,
and record the signup IP and user agent on the user row for later analysis.

None of these are individually strong. Together they raise the cost of a second
free review above ₹7,500, which is the actual goal.

### C.4 What not to do

- **Do not cripple the free review.** Doc §706 is explicit that the free review
  is complete and watermarked. The watermark (R-004 §B) is the differentiator;
  feature-gating is not.
- **Do not CAPTCHA the signup by default.** It suppresses genuine signups. Hold
  it in reserve behind a flag for when abuse is measured, not assumed.

## Behavior

- **B1** A real sender is required in production; startup fails without one.
- **B2** Every send is written to `notification_log` with a hashed recipient.
- **B3** Hard-bounced addresses are suppressed permanently.
- **B4** Signup sends a verification email; verification gates the free review,
  invitations and digests, and nothing else.
- **B5** Verification tokens are single-use and expire in 24 hours.
- **B6** Email changes verify the new address and notify the old.
- **B7** Disposable domains are rejected at signup with a clear message.
- **B8** Free reviews are counted per canonical email; canonicalisation never
  affects login.
- **B9** Every template is complete and actionable in plain text.

## Acceptance criteria

- **A1** `Settings(env="production")` with no SMTP config raises at startup.
- **A2** Signup writes a `notification_log` row with `template="verify_email"`.
- **A3** An unverified user can create an opportunity and upload, and gets
  `403 email_verification_required` on the free review.
- **A4** An unverified user who **pays** can run the review.
- **A5** A verification token works once; reuse and expiry return
  `400 invalid_verification_token`.
- **A6** Changing email does not change `users.email` until the new address is
  confirmed, and the old address receives a notice.
- **A7** Signup with `@mailinator.com` returns
  `400 disposable_email_not_allowed`.
- **A8** `alice+test@gmail.com` and `a.lice@gmail.com` share one free review.
- **A9** `alice+test@gmail.com` logs in with exactly the address as typed.
- **A10** A hard-bounced address receives no further sends.
- **A11** `/auth/verify-email/send` is limited to 3/hour per user.

## Out of scope

- WhatsApp delivery (MSG91, TS-035) — the `Message.channel` field is ready.
- Marketing email, preference centre, unsubscribe flows for transactional mail.
- Full email deliverability setup (SPF/DKIM/DMARC) — ops, tracked in R-016.

## Assumptions

- `assumption:` SMTP is the delivery mechanism, so the provider is swappable by
  configuration. If a provider's HTTP API is preferred later, it is a new adapter
  behind the same `Sender` protocol.
- `assumption:` The disposable-domain list is vendored and refreshed manually;
  a live lookup service is not worth the dependency at this stage.
