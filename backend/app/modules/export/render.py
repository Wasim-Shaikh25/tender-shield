"""Pure renderers for the Bid Review Pack (Doc §1.1(8), §11.4). No DB — take
plain data, return file bytes. Every export carries the review/date/pack stamp.

Free-tier watermark (Doc §7, R-004 §B): meta["watermark"] is decided
server-side by ExportService from the workspace's plan — never by the client
— and marks the DOCUMENT, never the content. Findings, quotes, page citations
and severities are identical between a free and a paid export; degrading them
would violate the quote-verification invariant and undercut the product's own
"crippled trials die in contractor WhatsApp groups" GTM (Doc §706) — the free
review is deliberately complete, so the watermark is the only thing that
distinguishes it from paid output.
"""

from __future__ import annotations

import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import RGBColor
from openpyxl import Workbook
from openpyxl.styles import Font

_SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
WATERMARK_TEXT = "FREE REVIEW — TenderShield — not for external issue"


def stamp_line(meta: dict) -> str:
    base = (
        f"Prepared with TenderShield · reviewed and approved on {meta.get('date', '')} "
        f"· pack {meta.get('pack', 'in-works')} · This is document-intelligence "
        f"software, not legal/QS advice — review with a qualified professional."
    )
    return f"{WATERMARK_TEXT} · {base}" if meta.get("watermark") else base


def render_xlsx(opportunity_title: str, findings: list[dict], meta: dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Risk Register"
    ws.append([f"Bid Review Pack — {opportunity_title}"])
    ws.append([stamp_line(meta)])
    ws.append([])
    ws.append(["Severity", "Category", "Title", "Review", "Page", "Source quote"])
    for f in sorted(findings, key=lambda x: _SEV_RANK.get(x.get("severity", "info"), 9)):
        ws.append(
            [
                f.get("severity"),
                f.get("category"),
                f.get("title"),
                f.get("review_status"),
                f.get("source_page"),
                f.get("source_quote"),
            ]
        )
    if meta.get("watermark"):
        # Repeated on every printed page (header/footer), not just row 1,
        # which a copy-paste into a new sheet would otherwise strip.
        ws.oddHeader.center.text = WATERMARK_TEXT
        ws.oddFooter.center.text = WATERMARK_TEXT
        ws["A1"].font = Font(bold=True, color="FFB91C1C")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _add_docx_watermark_header(doc: Document) -> None:
    """Repeats the watermark in the page header (every page), not just a
    top-of-document paragraph that a later page could be split away from."""
    header = doc.sections[0].header
    p = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    p.text = WATERMARK_TEXT
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.runs[0] if p.runs else p.add_run(WATERMARK_TEXT)
    run.bold = True
    run.font.color.rgb = RGBColor(0xB9, 0x1C, 0x1C)


def render_docx(
    opportunity_title: str, artifacts: list[dict], findings: list[dict], meta: dict
) -> bytes:
    doc = Document()
    if meta.get("watermark"):
        _add_docx_watermark_header(doc)
    doc.add_heading(f"Bid Review Pack — {opportunity_title}", level=0)
    doc.add_paragraph(stamp_line(meta)).italic = True

    accepted = [f for f in findings if f.get("review_status") in ("accepted", "edited")]
    doc.add_heading("Accepted risk findings", level=1)
    if accepted:
        table = doc.add_table(rows=1, cols=3)
        hdr = table.rows[0].cells
        hdr[0].text, hdr[1].text, hdr[2].text = "Severity", "Category", "Finding"
        for f in accepted:
            row = table.add_row().cells
            row[0].text = str(f.get("severity", ""))
            row[1].text = str(f.get("category", ""))
            row[2].text = str(f.get("title", ""))
    else:
        doc.add_paragraph("No accepted findings.")

    for art in artifacts:
        body = art.get("body", {})
        doc.add_heading(body.get("title", art.get("kind", "Artifact")), level=1)
        if body.get("preamble"):
            doc.add_paragraph(body["preamble"])
        for item in body.get("items", []):
            if art.get("kind") == "clarification_letter":
                doc.add_paragraph(f"{item.get('n')}. {item.get('heading', '')}", style=None)
                if item.get("quote"):
                    doc.add_paragraph(f"“{item['quote']}”").italic = True
                doc.add_paragraph(str(item.get("ask", "")))
            else:
                cat, txt = item.get("category"), item.get("assumption", "")
                doc.add_paragraph(f"{item.get('n')}. [{cat}] {txt}")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def render_pdf(
    opportunity_title: str, artifacts: list[dict], findings: list[dict], meta: dict
) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    small = ParagraphStyle("stamp", parent=normal, fontSize=8, textColor="#666666")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=f"Bid Review Pack — {opportunity_title}")
    flow = [
        Paragraph(f"Bid Review Pack — {opportunity_title}", styles["Title"]),
        Paragraph(stamp_line(meta), small),
        Spacer(1, 12),
        Paragraph("Accepted risk findings", styles["Heading2"]),
    ]

    accepted = [f for f in findings if f.get("review_status") in ("accepted", "edited")]
    if accepted:
        for f in sorted(accepted, key=lambda x: _SEV_RANK.get(x.get("severity", "info"), 9)):
            flow.append(
                Paragraph(
                    f"<b>[{f.get('severity')}]</b> {f.get('category')} — {f.get('title')}", normal
                )
            )
    else:
        flow.append(Paragraph("No accepted findings.", normal))

    for art in artifacts:
        b = art.get("body", {})
        flow.append(Spacer(1, 10))
        flow.append(Paragraph(b.get("title", art.get("kind", "Artifact")), styles["Heading2"]))
        if b.get("preamble"):
            flow.append(Paragraph(b["preamble"], normal))
        for item in b.get("items", []):
            if art.get("kind") == "clarification_letter":
                flow.append(Paragraph(f"{item.get('n')}. {item.get('heading', '')}", normal))
                if item.get("quote"):
                    flow.append(Paragraph(f"<i>“{item['quote']}”</i>", normal))
                flow.append(Paragraph(str(item.get("ask", "")), normal))
            else:
                cat, txt = item.get("category"), item.get("assumption", "")
                flow.append(Paragraph(f"{item.get('n')}. [{cat}] {txt}", normal))

    if meta.get("watermark"):
        doc.build(flow, onFirstPage=_stamp_pdf_page, onLaterPages=_stamp_pdf_page)
    else:
        doc.build(flow)
    return buf.getvalue()


def _stamp_pdf_page(canvas, doc) -> None:
    """Diagonal watermark drawn on every page (reportlab onPage callback) —
    a header/footer line alone is too easy to crop out of a PDF."""
    from reportlab.lib.pagesizes import A4

    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 40)
    canvas.setFillGray(0.85)
    canvas.translate(A4[0] / 2, A4[1] / 2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, "FREE REVIEW")
    canvas.restoreState()
