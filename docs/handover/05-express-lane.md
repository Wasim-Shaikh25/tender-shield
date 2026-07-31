# 05 — `express`: pay-per-report lane (TS-208 → TS-214)

**Spec:** `specs/modules/express-report.md`. **Sprint 5** in `tasks/phase16_tracker.md`.
Revenue lane / top of funnel — there is currently no `/pricing` page in `frontend/app/` and no
visitor funnel at all.

> ## ⚠️ Gate before you start
> The tracker sequences this **after Sprint 2 (correctness)** for a stated reason: this lane sells
> reports to strangers with **no reviewer in the loop**. Shipping it before M1 invariants pass on
> 1,000 real tenders is *"the single highest-liability sequencing error available in this plan."*
> Kill condition: **any invented quote reaching a customer → halt the Express lane immediately.**

---

## TS-208 — Module scaffold

`backend/app/modules/express/` — standard layout (`00-conventions.md` §2).

**The key architectural decision, and it removes most of the risk:** an Express session is backed by
an **ephemeral internal workspace**, so **all existing workspace-scoped isolation applies
unchanged**. No new isolation path is introduced. Do not invent a parallel "anonymous data" store.

```python
# service.py
def create_session(self, email: str, ack: Acknowledgment, ip: str) -> ExSession:
    workspace_id = self._create_ephemeral_workspace()   # real workspace row, flagged ephemeral
    token = secrets.token_urlsafe(32)                   # high-entropy, non-enumerable
    return self._persist(ExSession(
        token_hash=_hash(token),                        # store the HASH, never the raw token
        email=email, workspace_id=workspace_id,
        ack_text_version=ack.version, ack_at=utcnow(), ack_ip=ip,
        expires_at=utcnow() + timedelta(days=EXPRESS_SESSION_TTL_DAYS),
        state="created",
    )), token
```

```python
module = ModuleSpec(
    name="express", version="0.1.0", router=router,
    soft_deps=("ingestion", "risk", "boq", "export", "billing", "notifications", "auth"),
    setup=setup,
)
```

---

## TS-209 — Anonymous session lifecycle

**Tables**

```python
class ExSession(Base, WorkspaceScopedMixin):     # workspace_id = the ephemeral workspace
    _tablename_ = "ex_sessions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    tier: Mapped[str | None] = mapped_column(String, nullable=True)     # snapshot|risk|bidpack
    state: Mapped[str] = mapped_column(String, nullable=False, default="created")
    # acknowledgment record (acceptance A5)
    ack_text_version: Mapped[str] = mapped_column(String, nullable=False)
    ack_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ack_ip: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

class ExPurchase(Base, WorkspaceScopedMixin):
    _tablename_ = "ex_purchases"
    provider: Mapped[str] = mapped_column(String, nullable=False)       # razorpay|stripe
    provider_order_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # ^^ NULL until the verified webhook lands. This column IS the paywall.

class ExDocument(Base, WorkspaceScopedMixin):
    _tablename_ = "ex_documents"
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    retention_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

**Token handling:** return the raw token once, store only `sha256(token)`. Look up by hash. Tokens
must be **non-enumerable** (`secrets.token_urlsafe(32)`) and **expiring**.

**Upload size caps are enforced BEFORE buffering** — audit finding TS-I01 applies:

```python
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
content_length = int(request.headers.get("content-length") or 0)
if content_length > MAX_UPLOAD_BYTES:
    raise HTTPException(413, "file_too_large")     # reject before reading the body
```

---

## TS-210 — Teaser renderer

**Deliberately generous, because trust is the conversion event.** The teaser gives away real value:

| Give in full | Give as counts only |
|---|---|
| Deadline wall **with citations** (cheap to compute, highest perceived value) | Finding counts by severity and category |
| Missing-document checklist | BOQ defect count + total value affected |
| **Two complete findings** with verbatim quotes and page citations | everything else |

```python
def render_teaser(self, session: ExSession) -> dict:
    return {
        "deadlines": self._all_deadlines(session),          # FULL, with citations
        "missing_documents": self._missing_docs(session),   # FULL
        "finding_counts": self._counts_by_severity_and_category(session),
        "boq_defect_count": n, "boq_value_affected_minor": v, "currency": cur,
        "sample_findings": self._top_two_complete(session), # 2 complete, cited, quote-verified
        "locked": True,
    }
```

The two sample findings go through the **same quote verification** as any other finding — the kill
condition ("any invented quote reaching a customer") applies most sharply here, because this is the
output a stranger sees first.

---

## TS-211 — Server-owned prices + guest checkout — **P0**

**Audit finding TS-B01: the client never sends an amount.** Prices are a server-side table per
currency.

```python
# in billing, not express — express asks billing for a checkout
EXPRESS_PRICES_MINOR = {                 # assumption: validate against the first 100 transactions
    "INR": {"snapshot": 149900, "risk": 499900, "bidpack": 999900},
    # add other currencies explicitly; a missing currency is an error, not a fallback to INR
}

def create_express_checkout(tier: str, currency: str) -> Checkout:
    try:
        amount_minor = EXPRESS_PRICES_MINOR[currency][tier]
    except KeyError:
        raise BillingError("unknown_tier_or_currency")     # never guess a price
```

```python
def test_client_supplied_amount_is_rejected(client):
    r = client.post(f"/api/express/sessions/{token}/checkout",
                    json={"tier": "risk", "amount_minor": 1})     # attacker-supplied
    assert r.status_code in (400, 422)
    # and if it 200s, the created order MUST carry the server price, not 1
```

Razorpay Payment Links / guest checkout for India, Stripe for GCC/UK. No account required.

---

## TS-212 — Webhook-only activation — **P0**

**The single most important test in this module** — it is acceptance criterion A2 and Build Doc
§15.1:

```python
def test_report_locked_after_redirect_without_webhook(client):
    # 1. create session, upload, checkout
    # 2. simulate the client redirect returning "success" — the thing an attacker controls
    client.get(f"/api/express/sessions/{token}/return?payment_id=fake")
    # 3. the report MUST still be locked
    r = client.get(f"/api/express/sessions/{token}/report")
    assert r.status_code == 402, "client redirect activated a report — Build Doc §15.1 violated"

def test_report_unlocks_only_after_verified_webhook(client):
    _post_signed_webhook(client, order_id=order_id)      # signature-verified path
    assert client.get(f"/api/express/sessions/{token}/report").status_code == 200
```

Reuse the existing verified-webhook machinery in `app/modules/billing/` (Razorpay + Stripe verifiers
already exist, including the TS-B08 fix for the exception-swallowing verifier). Do not write a
second webhook path.

The report endpoint's gate is one line and should read as such:

```python
if purchase is None or purchase.activated_at is None:
    raise HTTPException(402, "payment_required")
```

---

## TS-213 — `unreviewed` export variant — **P0**, moat class 3

This is how the lane resolves the **Build Doc §11.4 conflict**: §11.4 gates export on reviewer
approval, and an Express buyer has no reviewer. The *intent* of §11.4 is that nobody relies on
unreviewed output unknowingly. So:

1. A distinct **`unreviewed`** export variant, watermarked
   **"INDICATIVE — NOT REVIEWED BY A QUALIFIED PROFESSIONAL"** on **every page of every format**
   (DOCX, PDF, XLSX).
2. Click-through acknowledgment **before payment**; text version + timestamp + IP recorded in the
   audit log.
3. **Pricing-intel outputs (loadings, cashflow) are excluded from every Express tier** — the
   highest-liability outputs require a reviewer.
4. The disclaimer appears in the **emailed PDF**, not only the web view.
5. The report states plainly that findings are machine-generated and require professional review.

```python
def test_every_express_export_format_is_watermarked():
    for fmt in ("docx", "pdf", "xlsx"):
        blob = render_export(session, fmt=fmt, variant="unreviewed")
        assert WATERMARK_TEXT in _extract_all_text(blob)

def test_pricing_never_appears_in_any_express_tier():
    for tier in ("snapshot", "risk", "bidpack"):
        report = render_report(session, tier=tier)
        assert "loadings" not in report and "cashflow" not in report
```

---

## TS-214 — Anti-abuse, retention, claim

**Anti-abuse**
- Rate limits per email, per IP, per `document_hash` (reuse `app/core/ratelimit.py`).
- **An identical `document_hash` does not generate a second free teaser** — this is the main
  free-value leak; dedupe on the hash, not on the filename.
- Daily teaser cap per IP.
- Email verification required before teaser render if the abuse rate exceeds a configured threshold.
- **Express sessions do not consume the org free-tier review allowance, and vice versa.**

**Retention** — documents and findings deleted after a configured window (`assumption:` 90 days)
unless claimed. *"Tender documents are competitively sensitive (Build Doc §1.3) — retention is a
promise, not a default."* State it in-product **before** upload. Implement as a scheduled job via
`app/core/scheduler.py`, and test that it actually deletes.

**Claim** — a magic link converts the session into a real workspace, carrying documents and findings
**without data loss**. Because the session was already backed by a real (ephemeral) workspace, this
is largely a re-parenting operation rather than a data migration.

```python
def test_claim_migrates_everything(client):
    doc_ids_before   = _document_ids(session)
    finding_ids_before = _finding_ids(session)
    workspace_id = claim(session, user)
    assert _document_ids_in(workspace_id) == doc_ids_before
    assert _finding_ids_in(workspace_id) == finding_ids_before
```

---

## Full acceptance checklist (spec §Acceptance criteria — all 11)

1. Session created, documents uploaded, teaser rendered — **no authentication**.
2. Full report unreachable until a verified webhook marks the purchase active (redirect-before-webhook test).
3. Prices server-owned; client-supplied amount rejected.
4. Every Express export watermarked `unreviewed` in DOCX, PDF and XLSX.
5. Acknowledgment recorded with text version, timestamp, IP; queryable in the audit log.
6. Pricing-intel outputs never appear in any Express tier — asserted by test.
7. Session tokens high-entropy, expiring, non-enumerable.
8. An Express session cannot read another session's or workspace's data.
9. Claiming migrates documents and findings without data loss.
10. Express usage does not decrement any org's free-tier allowance.
11. Retention deletion runs and is verified by test.
