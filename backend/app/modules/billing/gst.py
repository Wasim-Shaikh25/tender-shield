"""GST invoice computation (Doc §15.8) — pure. CGST+SGST for intra-state
(buyer's GSTIN state == seller's), else IGST. SAC 998313. Amounts in paise.

R-007/TS-096: catalog prices in plans.PRICES_MINOR are treated as
GST-inclusive (the number a customer sees is the number they pay — no
"+ GST" surprise at checkout) — `compute_invoice_from_inclusive_total` backs
out the taxable base and tax lines from that inclusive total, with any
±1 paise rounding residue landing in an explicit round-off line so
base + taxes + round_off == total exactly. `compute_invoice` (pre-tax base
-> inclusive total) is kept for anything computed the other direction."""

from __future__ import annotations

from dataclasses import dataclass

SAC_CODE = "998313"
GST_RATE = 18  # percent

# GSTIN state codes are 01-38 (Doc §15.8 assumption — Indian union/state codes).
_VALID_STATE_CODES = {f"{i:02d}" for i in range(1, 39)}
_GSTIN_CHECKSUM_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


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
    round_off_minor: int
    total_minor: int
    intra_state: bool


def _state_of(gstin: str | None) -> str | None:
    return gstin[:2] if gstin and len(gstin) >= 2 else None


def _tax_lines(base_minor: int, *, intra: bool) -> list[GstLine]:
    if intra:
        half = GST_RATE // 2
        cgst = base_minor * half // 100
        sgst = base_minor * half // 100
        return [GstLine("CGST", half, cgst), GstLine("SGST", half, sgst)]
    igst = base_minor * GST_RATE // 100
    return [GstLine("IGST", GST_RATE, igst)]


def compute_invoice(
    *, number: str, base_minor: int, buyer_gstin: str | None, seller_state_code: str
) -> GstInvoice:
    """base_minor is pre-tax; the total is derived by ADDING tax on top, so it
    is exact by construction (round_off_minor is always 0 here)."""
    intra = _state_of(buyer_gstin) == seller_state_code
    lines = _tax_lines(base_minor, intra=intra)
    total = base_minor + sum(line.amount_minor for line in lines)
    return GstInvoice(
        number=number,
        sac=SAC_CODE,
        base_minor=base_minor,
        lines=lines,
        round_off_minor=0,
        total_minor=total,
        intra_state=intra,
    )


def compute_invoice_from_inclusive_total(
    *, number: str, total_minor: int, buyer_gstin: str | None, seller_state_code: str
) -> GstInvoice:
    """total_minor is what was actually charged (GST-inclusive catalog price,
    R-005/R-007) — the base and tax lines are backed OUT of it, so integer
    division can leave a ±1 paise residue. That residue is captured explicitly
    in `round_off_minor` rather than silently dropped, so
    base + sum(lines) + round_off_minor == total_minor always holds exactly
    (R-007 §B.5)."""
    intra = _state_of(buyer_gstin) == seller_state_code
    base = (total_minor * 100) // (100 + GST_RATE)
    lines = _tax_lines(base, intra=intra)
    round_off = total_minor - (base + sum(line.amount_minor for line in lines))
    return GstInvoice(
        number=number,
        sac=SAC_CODE,
        base_minor=base,
        lines=lines,
        round_off_minor=round_off,
        total_minor=total_minor,
        intra_state=intra,
    )


def invoice_number(seq: int, *, prefix: str = "TS", fy: str = "2026-27") -> str:
    """Sequential, gap-free statutory number, e.g. TS/2026-27/000042."""
    return f"{prefix}/{fy}/{seq:06d}"


def financial_year(when) -> str:
    """Indian FY runs April-March: 2026-04-01 -> '2026-27'."""
    y = when.year if when.month >= 4 else when.year - 1
    return f"{y}-{str(y + 1)[-2:]}"


def gstin_check_digit(gstin_without_check_digit: str) -> str:
    """A mod-36 weighted check digit over the first 13 characters (state+PAN+
    entity code — not the fixed 'Z' at position 13), right to left with an
    alternating 2/1 multiplier.

    assumption: this reproduces the STRUCTURE of GSTN's published check-digit
    scheme (mod-36 Luhn-like, same alphabet as the PAN check digit), but has
    NOT been verified against real GSTN reference vectors — this sandbox has
    no way to confirm the exact multiplier direction/starting factor against
    an authoritative source. Treat the checksum as self-consistent (it will
    reliably catch a typo'd/transposed GSTIN, since format_ok(g) implies
    gstin_check_digit reproduces g's own check digit) rather than as proof a
    given GSTIN is real. Confirm against GSTN's published spec — or swap in a
    verified library — before this gates a live paid checkout (same posture
    as the SAC-rate assumption below: a decision to verify, not to derive).
    """
    factor = 2
    total = 0
    for ch in reversed(gstin_without_check_digit[:13]):
        digit = factor * _GSTIN_CHECKSUM_ALPHABET.index(ch)
        total += digit // 36 + digit % 36
        factor = 1 if factor == 2 else 2
    return _GSTIN_CHECKSUM_ALPHABET[(36 - (total % 36)) % 36]


def validate_gstin(gstin: str) -> bool:
    """Format + checksum validation (15 chars: 2-digit state, 10-char PAN,
    entity code, 'Z', check digit) — an invalid GSTIN on an invoice is worse
    than none (R-007 §B.1), so this is checked at save time, not just format.
    See `gstin_check_digit`'s docstring for the checksum's verification status.
    """
    if len(gstin) != 15:
        return False
    if gstin[0:2] not in _VALID_STATE_CODES:
        return False
    body = gstin[2:12]
    pan_ok = (
        body[:5].isalpha() and body[:5].isupper() and body[5:9].isdigit() and body[9].isalpha()
    )
    if not pan_ok:
        return False  # PAN shape: AAAAA9999A
    entity = gstin[12]
    entity_ok = entity.isdigit() or (entity.isalpha() and entity.isupper())
    if not entity_ok:
        return False  # entity/registration count within a PAN+state: 1-9, then A-Z
    if gstin[13] != "Z":
        return False
    return gstin_check_digit(gstin[:14]) == gstin[14]
