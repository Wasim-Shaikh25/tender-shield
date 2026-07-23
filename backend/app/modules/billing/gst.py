"""GST invoice computation (Doc §15.8) — pure. CGST+SGST for intra-state
(buyer's GSTIN state == seller's), else IGST. SAC 998313. Amounts in paise.
Issuance-on-payment (PDF + email + persistence) is a follow-up; this is the
tax-correct computation + sequential numbering it depends on."""

from __future__ import annotations

from dataclasses import dataclass

SAC_CODE = "998313"
GST_RATE = 18  # percent


@dataclass
class GstLine:
    name: str  # CGST | SGST | IGST
    rate_pct: int
    amount_minor: int


@dataclass
class GstInvoice:
    number: str
    sac: str
    base_minor: int
    lines: list[GstLine]
    total_minor: int
    intra_state: bool


def _state_of(gstin: str | None) -> str | None:
    return gstin[:2] if gstin and len(gstin) >= 2 else None


def compute_invoice(
    *, number: str, base_minor: int, buyer_gstin: str | None, seller_state_code: str
) -> GstInvoice:
    intra = _state_of(buyer_gstin) == seller_state_code
    if intra:
        half = GST_RATE // 2
        cgst = base_minor * half // 100
        sgst = base_minor * half // 100
        lines = [GstLine("CGST", half, cgst), GstLine("SGST", half, sgst)]
    else:
        igst = base_minor * GST_RATE // 100
        lines = [GstLine("IGST", GST_RATE, igst)]
    total = base_minor + sum(line.amount_minor for line in lines)
    return GstInvoice(
        number=number, sac=SAC_CODE, base_minor=base_minor, lines=lines,
        total_minor=total, intra_state=intra,
    )


def invoice_number(seq: int, *, prefix: str = "TS", fy: str = "2026-27") -> str:
    """Sequential, gap-free statutory number, e.g. TS/2026-27/000042."""
    return f"{prefix}/{fy}/{seq:06d}"
