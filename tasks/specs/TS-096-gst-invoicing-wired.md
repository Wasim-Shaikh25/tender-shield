# TS-096 — GST invoicing: wire `gst.py`, tax columns, gap-free FY series, PDF, credit notes

**Status:** done
**Requirement:** [R-007](../../specs/requirements/R-007-gst-invoicing.md)
**Spec(s) updated:** `specs/modules/billing.md`
**Module(s):** `billing`
**Severity / Gate:** P1 · Gate 1

## What this builds

TS-029 built correct GST *computation* (`gst.py`), but `create_invoice`
never called it. Invoices were one flat number with no tax breakdown, a
global `uuid.uuid4().hex`-then-`INV-{id:06d}` numbering scheme (not the
statutory FY series, and a global sequence that leaks total customer count
via gaps), no PDF, and no credit notes.

## Current (the defects)

```python
# backend/app/modules/billing/service.py:89 (before this task)
def create_invoice(self, workspace_id, *, amount_minor, ...):
    inv = Invoice(
        invoice_number=uuid.uuid4().hex,        # temporary placeholder
        amount_minor=amount_minor,              # one number, no tax breakdown
    )
    inv.invoice_number = f"INV-{inv.id:06d}"    # not the statutory FY series
```

## Implementation

```python
# backend/app/modules/billing/models.py — Invoice gains real GST columns
base_minor, discount_minor, cgst_minor, sgst_minor, igst_minor, total_minor,
sac_code, seller_gstin, buyer_gstin, buyer_legal_name, place_of_supply,
round_off_minor, fy, seq, doc_type ("invoice"|"credit_note"), original_invoice_id
# Snapshotted ONTO the invoice at issuance, never joined to workspace at
# render time — an invoice is a statutory record of a moment.
```

```python
# gap-free per-FY numbering — a Postgres SEQUENCE would leak numbers on rollback
class InvoiceSequence(Base):
    __tablename__ = "invoice_sequences"
    fy: Mapped[str] = mapped_column(String, primary_key=True)
    last_seq: Mapped[int] = mapped_column(Integer, default=0)

def _next_seq(self, fy: str) -> int:
    row = self.s.execute(select(InvoiceSequence).where(InvoiceSequence.fy == fy)
        .with_for_update()).scalar_one_or_none()   # serializes issuance per FY
    ...
    row.last_seq += 1
    return row.last_seq
```

```python
def issue_invoice(self, intent: PaymentIntent, event: ProviderEvent) -> Invoice:
    """Tax computed on the DISCOUNTED base (R-006 §B.3) — GST follows the
    consideration actually paid, not the list price."""
    computed = compute_invoice(number=invoice_number(seq, ...),
        base_minor=intent.list_amount_minor - intent.discount_minor,
        buyer_gstin=workspace.gstin, seller_state_code=self._settings.seller_state_code)
    inv = Invoice(..., cgst_minor=lines.get("CGST", 0), sgst_minor=lines.get("SGST", 0),
                  igst_minor=lines.get("IGST", 0), total_minor=computed.total_minor, ...)
    self.s.flush()
    inv.pdf_key = self._render_and_store_pdf(inv, workspace)
    self.s.commit()
    self._email_invoice(inv, workspace)
    return inv
```

Reconciliation check: `inv.total_minor` must equal `intent.amount_minor` —
if they differ, tax computed at checkout diverged from tax computed at
issuance; logs loudly and alerts rather than issuing a wrong invoice.
Credit notes (`issue_credit_note`) reference the original invoice in the
same series, with GST apportioned at the same rate for partial refunds.
`round_off_minor` absorbs the ±1 paise floor-division difference so
`base + taxes + round_off == total` exactly. PDF served via
`GET /api/billing/invoices/{id}/pdf` (workspace-scoped, not a public URL).

## Files touched

- `backend/app/modules/billing/{models,service,gst,pdf,router}.py`
- `backend/migrations/versions/e4587e477606_gst_invoicing.py`

## Tests

- `backend/tests/modules/billing/test_gst.py::test_issue_invoice_reconciliation`,
  `test_credit_note_apportionment`, `test_gapfree_fy_sequence_under_rollback`

## Acceptance criteria (billing.md A14–A19)

- [x] Every issued invoice has a gap-free per-FY sequence number, even under
      concurrent issuance / rollback.
- [x] `base + taxes + round_off == total` exactly for every invoice.
- [x] A refund produces a credit note in the same series referencing the
      original invoice.

## Commit

Predates commit-granular history (PR #10 bulk import).
