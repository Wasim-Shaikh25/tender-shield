"""GST tax-invoice PDF rendering (R-007 §B.6). Rendered on demand from the
Invoice row's own (already snapshotted) fields — never pre-rendered/stored,
so there is no separate artifact to keep in sync with the statutory record
and no dependency on a cross-module storage capability (`ingestion.storage`
is ingestion's own; billing may not import it, CLAUDE.md §2)."""

from __future__ import annotations

import io

from app.modules.billing.models import Invoice

_ONES = (
    "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
)
_TENS = (
    "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
)


def _two_digit_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + (f" {_ONES[ones]}" if ones else "")


def _three_digit_words(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{_ONES[hundreds]} hundred")
    if rest:
        parts.append(_two_digit_words(rest))
    return " ".join(parts) if parts else "zero"


def rupees_in_words(paise: int) -> str:
    """Indian numbering system (lakh/crore) rupees-and-paise, in words —
    required on a compliant tax invoice alongside figures (R-007 §B.6)."""
    rupees, remainder_paise = divmod(abs(paise), 100)
    groups = []
    crore, rest = divmod(rupees, 1_00_00_000)
    if crore:
        groups.append(f"{_three_digit_words(crore)} crore")
    lakh, rest = divmod(rest, 1_00_000)
    if lakh:
        groups.append(f"{_three_digit_words(lakh)} lakh")
    thousand, rest = divmod(rest, 1_000)
    if thousand:
        groups.append(f"{_three_digit_words(thousand)} thousand")
    if rest:
        groups.append(_three_digit_words(rest))
    rupee_words = " ".join(groups) if groups else "zero"
    words = f"rupees {rupee_words}"
    if remainder_paise:
        words += f" and {_two_digit_words(remainder_paise)} paise"
    sign = "minus " if paise < 0 else ""
    return f"{sign}{words} only".capitalize()


def render_invoice_pdf(invoice: Invoice, *, seller_legal_name: str, seller_address: str) -> bytes:
    """A compliant tax invoice states: the words "Tax Invoice"/"Credit Note";
    seller name, address and GSTIN; invoice number and date; buyer name and
    GSTIN; place of supply; SAC; taxable value; each tax head's rate and
    amount; total in figures and words; and a computer-generated statement in
    lieu of a signature (R-007 §B.6)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    small = ParagraphStyle("small", parent=normal, fontSize=8, textColor="#555555")

    doc_title = "Credit Note" if invoice.doc_type == "credit_note" else "Tax Invoice"
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=f"{doc_title} {invoice.invoice_number}")

    flow = [
        Paragraph(doc_title, styles["Title"]),
        Paragraph(
            f"{invoice.invoice_number} &nbsp;&middot;&nbsp; {invoice.created_at:%d %b %Y}", normal
        ),
        Spacer(1, 10),
        Paragraph(f"<b>{seller_legal_name}</b>", normal),
        Paragraph(seller_address or "", normal),
        Paragraph(f"GSTIN: {invoice.seller_gstin or 'unregistered'}", normal),
        Spacer(1, 10),
        Paragraph(f"<b>Billed to:</b> {invoice.buyer_legal_name or '-'}", normal),
        Paragraph(f"GSTIN: {invoice.buyer_gstin or 'unregistered (B2C)'}", normal),
        Paragraph(f"Place of supply: {invoice.place_of_supply or '-'}", normal),
        Spacer(1, 14),
    ]

    if invoice.doc_type == "credit_note" and invoice.original_invoice_id:
        flow.append(Paragraph(f"Against invoice #{invoice.original_invoice_id}", normal))
        flow.append(Spacer(1, 6))

    rows = [["Description", "SAC", "Taxable value"]]
    rows.append(
        [
            "TenderShield subscription/service",
            invoice.sac_code,
            _money(invoice.base_minor, invoice.currency),
        ]
    )
    if invoice.cgst_minor:
        rows.append(["CGST @ 9%", "", _money(invoice.cgst_minor, invoice.currency)])
    if invoice.sgst_minor:
        rows.append(["SGST @ 9%", "", _money(invoice.sgst_minor, invoice.currency)])
    if invoice.igst_minor:
        rows.append(["IGST @ 18%", "", _money(invoice.igst_minor, invoice.currency)])
    if invoice.round_off_minor:
        rows.append(["Round off", "", _money(invoice.round_off_minor, invoice.currency)])
    rows.append(["Total", "", _money(invoice.total_minor, invoice.currency)])

    table = Table(rows, colWidths=[260, 80, 120])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, "#333333"),
                ("LINEABOVE", (0, -1), (-1, -1), 0.5, "#333333"),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ]
        )
    )
    flow.append(table)
    flow.append(Spacer(1, 10))
    flow.append(Paragraph(f"<b>{rupees_in_words(invoice.total_minor)}</b>", normal))
    flow.append(Spacer(1, 20))
    flow.append(
        Paragraph("This is a computer-generated document and does not require a signature.", small)
    )

    doc.build(flow)
    return buf.getvalue()


def _money(paise: int, currency: str) -> str:
    symbol = "₹" if currency == "INR" else currency + " "
    return f"{symbol}{paise / 100:,.2f}"
