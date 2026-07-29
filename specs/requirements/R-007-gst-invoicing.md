# R-007 — GST invoicing: wire the dead code, add tax columns, issue PDFs

**Status:** implemented — tax-correct invoices issued on payment success,
gap-free per-FY numbering (verified under real Postgres concurrency),
credit notes on refund, GSTIN capture + format/checksum validation, and an
on-demand PDF route. Two deliberate deviations from this draft: (1) catalog
prices are treated as GST-**inclusive** rather than tax-added-on-top, so the
checkout amount never changes and the tax breakdown is derived from it
(§B.4 below, superseding the draft's "issue_invoice recomputes and
reconciles" design — the reconciliation is now true by construction); (2)
PDFs render on demand rather than being pre-rendered and stored via the
`Storage` protocol, since `billing` cannot import `ingestion.storage`
(CLAUDE.md §2) and no cross-module storage capability exists yet. GSTIN
checksum validation is self-consistent but unverified against a real GSTN
reference (see `gst.py`'s docstring) — flagged for confirmation before it
gates a live paid checkout, same posture as the SAC-rate assumption below.
See `specs/modules/billing.md` B5 and A14-A19 for the full account.
**Severity:** P1 — Indian B2B customers cannot claim input credit
**Requirement refs:** Doc §15.8
**Task refs:** TS-096
**Task files:** code-level detail (current-vs-target snippets, file:line, files touched, tests) now lives per-task, split out by TS-126's restructure: [TS-096](../../tasks/specs/TS-096-gst-invoicing-wired.md). This document stays the business/behavior-level record (purpose, target behavior, acceptance criteria).

**Gap refs:** `docs/GAP_ANALYSIS.md` §2.6
**Specs to update:** `specs/modules/billing.md`

## Purpose

`backend/app/modules/billing/gst.py` implements CGST/SGST vs IGST correctly and
generates the statutory `TS/2026-27/000042` number format. Its only importer is
`tests/test_hardening.py:19`. Real invoices go through a different, tax-unaware
path — so a GST-registered customer cannot claim input credit, which makes the
product hard to expense and hard to sell to exactly the mid-market GCs who are
persona P1.

## Current

```python
# backend/app/modules/billing/service.py:89
def create_invoice(self, workspace_id, *, amount_minor, currency="INR",
                   provider="manual", provider_invoice_id=None, raw=None, status="pending"):
    inv = Invoice(
        workspace_id=uuid.UUID(str(workspace_id)),
        invoice_number=uuid.uuid4().hex,        # temporary placeholder
        amount_minor=amount_minor,              # ← one number, no tax breakdown
        ...
    )
    self.s.add(inv)
    self.s.flush()
    inv.invoice_number = f"INV-{inv.id:06d}"    # ← not the statutory FY series
```

Defects:

1. `compute_invoice` and `invoice_number` from `gst.py` are never called.
2. `Invoice` (`models.py:56`) has no `base_minor`, no CGST/SGST/IGST columns, no
   buyer GSTIN, no place of supply, no SAC code.
3. `INV-{id:06d}` is a **global** sequence — gaps appear across workspaces and
   the total customer count leaks to any customer who reads their own number.
4. No PDF is rendered and nothing is emailed.
5. No credit notes for refunds.

## Target

### B.1 Seller and buyer identity

Seller details are configuration, not code:

```python
# backend/app/core/config.py
    seller_legal_name: str = "TenderShield Technologies Private Limited"
    seller_gstin: str = ""                 # e.g. 27AAAAA0000A1Z5
    seller_state_code: str = "27"          # first 2 digits of the GSTIN
    seller_address: str = ""
    invoice_series_prefix: str = "TS"
```

Buyer details live on the workspace — a GSTIN is required before a paid checkout
completes for an Indian workspace, because it cannot be added to an invoice
retroactively:

```python
# backend/app/modules/auth/models.py — Workspace
legal_name: Mapped[str | None] = mapped_column(String, nullable=True)
gstin: Mapped[str | None] = mapped_column(String, nullable=True)
billing_address: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
place_of_supply: Mapped[str | None] = mapped_column(String, nullable=True)  # state code
```

Validate the GSTIN format (15 chars, `NN AAAAA NNNN A N Z N`) and verify its
checksum before saving. An invalid GSTIN on an invoice is worse than none.

### B.2 Invoice columns

```python
class Invoice(Base, WorkspaceScopedMixin):
    _tablename_ = "invoices"
    id: Mapped[int] = mapped_column(_BigId, primary_key=True, autoincrement=True)

    invoice_number: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    fy: Mapped[str] = mapped_column(String, nullable=False)           # "2026-27"
    seq: Mapped[int] = mapped_column(Integer, nullable=False)         # per-FY sequence
    doc_type: Mapped[str] = mapped_column(String, nullable=False, default="invoice")
    # invoice | credit_note
    original_invoice_id: Mapped[int | None] = mapped_column(_BigId, nullable=True)

    base_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)       # pre-tax, post-discount
    discount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cgst_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sgst_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    igst_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="INR")

    sac_code: Mapped[str] = mapped_column(String, nullable=False, default="998313")
    seller_gstin: Mapped[str | None] = mapped_column(String, nullable=True)
    buyer_gstin: Mapped[str | None] = mapped_column(String, nullable=True)
    buyer_legal_name: Mapped[str | None] = mapped_column(String, nullable=True)
    place_of_supply: Mapped[str | None] = mapped_column(String, nullable=True)
    reverse_charge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    payment_intent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_invoice_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pdf_key: Mapped[str | None] = mapped_column(String, nullable=True)   # object-storage key
    status: Mapped[str] = mapped_column(String, nullable=False, default="issued")
    raw: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Snapshot `seller_gstin`, `buyer_gstin` and `buyer_legal_name` **onto the invoice**
rather than joining to the workspace at render time. An invoice is a statutory
record of a moment; if the customer later changes their registered name, the
issued invoice must not change with it.

### B.3 Gap-free per-FY numbering

GST requires a consecutive series. The current global auto-increment produces
gaps whenever a transaction rolls back.

```python
class InvoiceSequence(Base):
    """One row per financial year. Gap-free numbering requires the sequence to
    advance inside the same transaction that inserts the invoice — a Postgres
    SEQUENCE would leak numbers on rollback (R-007 §B.3)."""

    __tablename__ = "invoice_sequences"
    fy: Mapped[str] = mapped_column(String, primary_key=True)
    last_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


def _next_seq(self, fy: str) -> int:
    row = self.s.execute(
        select(InvoiceSequence).where(InvoiceSequence.fy == fy).with_for_update()
    ).scalar_one_or_none()
    if row is None:
        row = InvoiceSequence(fy=fy, last_seq=0)
        self.s.add(row)
        self.s.flush()
    row.last_seq += 1
    return row.last_seq


def _financial_year(when: datetime) -> str:
    """Indian FY runs April–March: 2026-04-01 → '2026-27'."""
    y = when.year if when.month >= 4 else when.year - 1
    return f"{y}-{str(y + 1)[-2:]}"
```

`SELECT ... FOR UPDATE` serialises issuance per FY. That is a deliberate
bottleneck — invoice issuance is low-volume and correctness beats throughput.

### B.4 Issuance on payment

```python
def issue_invoice(self, intent: PaymentIntent, event: ProviderEvent) -> Invoice:
    """Issue a GST invoice when a payment succeeds (Doc §15.8).

    Tax is computed on the DISCOUNTED base (R-006 §B.3) — GST follows the
    consideration actually paid, not the list price.
    """
    workspace = self._workspaces().get(intent.workspace_id)
    now = datetime.now(UTC)
    fy = _financial_year(now)
    seq = self._next_seq(fy)

    computed = compute_invoice(
        number=invoice_number(seq, prefix=self._settings.invoice_series_prefix, fy=fy),
        base_minor=intent.list_amount_minor - intent.discount_minor,
        buyer_gstin=workspace.gstin,
        seller_state_code=self._settings.seller_state_code,
    )

    lines = {line.name: line.amount_minor for line in computed.lines}
    inv = Invoice(
        workspace_id=intent.workspace_id,
        invoice_number=computed.number, fy=fy, seq=seq,
        base_minor=computed.base_minor,
        discount_minor=intent.discount_minor,
        cgst_minor=lines.get("CGST", 0),
        sgst_minor=lines.get("SGST", 0),
        igst_minor=lines.get("IGST", 0),
        total_minor=computed.total_minor,
        currency=intent.currency, sac_code=computed.sac,
        seller_gstin=self._settings.seller_gstin,
        buyer_gstin=workspace.gstin,
        buyer_legal_name=workspace.legal_name or workspace.name,
        place_of_supply=workspace.place_of_supply or _state_of(workspace.gstin),
        payment_intent_id=intent.id, provider=intent.provider,
        provider_invoice_id=event.event_id, status="paid", paid_at=now,
    )
    self.s.add(inv)
    self.s.flush()
    inv.pdf_key = self._render_and_store_pdf(inv, workspace)
    self.s.commit()
    self._email_invoice(inv, workspace)
    return inv
```

**Reconciliation check:** `inv.total_minor` must equal `intent.amount_minor`.
If they differ, the tax computed at checkout (R-005 §B.2) diverged from the tax
computed at issuance — log loudly and alert rather than issuing a wrong invoice.

### B.5 Credit notes

A refund needs a credit note referencing the original invoice, in the same
series:

```python
def issue_credit_note(self, original: Invoice, amount_minor: int) -> Invoice:
    ...
    doc_type="credit_note", original_invoice_id=original.id,
    # amounts stored positive; the doc_type carries the sign
```

Partial refunds produce a credit note for the refunded portion only, with GST
apportioned at the same rate.

### B.6 PDF rendering

Reuse `reportlab`, already a dependency (`pyproject.toml`). A compliant tax
invoice must show: the words "Tax Invoice"; seller name, address and GSTIN;
invoice number and date; buyer name, address and GSTIN; place of supply; SAC
998313; description; taxable value; rate and amount of each tax head; total in
figures and words; and a signature or the statement that it is
computer-generated.

Store the PDF via the `Storage` protocol (`ingestion/storage.py:12`, S3 in
production per R-016) and serve it through an authorized route rather than a
public URL:

```
GET /api/billing/invoices/{id}/pdf     (viewer, workspace-scoped)
```

### B.7 Edge cases that must be handled

| Case | Rule |
|---|---|
| Buyer has no GSTIN (B2C) | Treat as inter-state or intra-state by billing address; no input credit; still a valid invoice |
| Buyer state == seller state | CGST + SGST (`gst.py` already correct) |
| Buyer state ≠ seller state | IGST |
| Export of service (non-India) | Zero-rated; `reverse_charge=False`, no GST lines — needs Stripe (R-005) |
| Rounding | `gst.py` floor-divides; the ±1 paise rounding difference goes to a `round_off_minor` column so `base + taxes + round_off == total` exactly |

The rounding column matters: without it, `base + cgst + sgst != total` for many
amounts and accountants reject the invoice.

## Behavior

- **B1** Every successful payment issues exactly one invoice, in the FY series,
  with a gap-free per-FY sequence.
- **B2** Tax is computed on the discounted base, by `gst.py`, never by an LLM and
  never in floats.
- **B3** Intra-state → CGST+SGST; inter-state → IGST; the split is derived from
  the buyer's GSTIN state vs the seller's.
- **B4** Buyer and seller identity are snapshotted onto the invoice at issuance.
- **B5** `base_minor + all taxes + round_off_minor == total_minor` exactly.
- **B6** `total_minor` equals the `payment_intents.amount_minor` that was
  charged; a mismatch alerts and blocks issuance.
- **B7** Refunds issue a credit note in the same series referencing the original.
- **B8** Invoice PDFs are stored and served only to members of the owning
  workspace.
- **B9** An Indian workspace must supply a valid GSTIN (or explicitly declare
  itself unregistered) before a paid checkout completes.

## Acceptance criteria

- **A1** `create_invoice` no longer exists in its untaxed form; every invoice row
  has non-zero tax columns for a taxable supply.
- **A2** Buyer GSTIN `27...`, seller state `27` → CGST 9% + SGST 9%, IGST 0.
- **A3** Buyer GSTIN `29...`, seller state `27` → IGST 18%, CGST/SGST 0.
- **A4** Invoice numbers for FY 2026-27 are `TS/2026-27/000001`, `…/000002`, with
  no gaps, including after a rolled-back transaction.
- **A5** Concurrent issuance produces no duplicate sequence numbers.
- **A6** `base + cgst + sgst + igst + round_off == total` for 1,000 randomly
  generated amounts (property test).
- **A7** A ₹24,999 Pro subscription with a 25% coupon produces base 1,874,925,
  IGST 337,486, total 2,212,411 (±1 paise absorbed by round-off) and matches the
  charged amount.
- **A8** A refund produces a credit note whose `original_invoice_id` points at
  the invoice and whose taxes are apportioned at the same rate.
- **A9** A member of another workspace requesting an invoice PDF gets `404`.
- **A10** An invalid GSTIN checksum is rejected at save time.

## Out of scope

- E-invoicing / IRN registration with the GST portal (mandatory above a turnover
  threshold this product will not hit in Phase 1 — revisit before it does).
- GSTR-1 filing exports.
- TDS/TCS handling.
- Multi-currency tax (VAT for GCC/UK) — arrives with Stripe.

## Assumptions

- `assumption:` SAC 998313 ("Information technology consulting and support
  services") at 18% is correct for this product. Confirm with the company's CA
  before the first live invoice — this is a decision to verify, not to derive.
- `assumption:` The seller is registered in one state only. Multi-state
  registration would require per-state series.
