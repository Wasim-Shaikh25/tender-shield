# TS-029 — GST invoice computation (CGST/SGST vs IGST, sequential numbering)

**Status:** done
**Requirement:** Doc §15.8
**Spec(s) updated:** `specs/modules/billing.md`
**Module(s):** `billing`
**Severity / Gate:** P1 · Phase 1 MVP

## What this builds

Correct Indian GST invoicing: intra-state (CGST+SGST) vs inter-state (IGST)
split by comparing GSTIN state codes, legally-required sequential invoice
numbering per financial year, and GSTIN checksum validation — deterministic
tax math, never LLM-computed (CLAUDE.md §4).

## Implementation

```python
# backend/app/modules/billing/gst.py
def _state_of(gstin: str | None) -> str | None: ...
def _tax_lines(base_minor: int, *, intra: bool) -> list[GstLine]: ...
def compute_invoice(...) -> GstInvoice: ...
def compute_invoice_from_inclusive_total(...) -> GstInvoice: ...

def invoice_number(seq: int, *, prefix: str = "TS", fy: str = "2026-27") -> str: ...
def financial_year(when) -> str: ...

def gstin_check_digit(gstin_without_check_digit: str) -> str: ...
def validate_gstin(gstin: str) -> bool: ...
```

```python
# backend/app/modules/billing/models.py
class Invoice(Base, WorkspaceScopedMixin): ...
class InvoiceSequence(Base): ...   # guarantees gapless sequential numbering
```

All amounts are in paise (`base_minor`) throughout — never float.

## Files touched

- `backend/app/modules/billing/{gst,models,service,router}.py`

## Tests

- `backend/tests/modules/billing/test_gst.py`

## Acceptance criteria

- [x] Same-state billing produces CGST+SGST; cross-state produces IGST.
- [x] Invoice numbers are sequential within a financial year, never reused
      or skipped.
- [x] A malformed GSTIN checksum is rejected by `validate_gstin`.

## Commit

Predates commit-granular history (PR #10 bulk import).
