"""Pure renderers for the Bid Review Pack (Doc §1.1(8), §11.4). No DB — take
plain data, return file bytes. Every export carries the review/date/pack stamp."""

from __future__ import annotations

import io

from docx import Document
from openpyxl import Workbook

_SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def stamp_line(meta: dict) -> str:
    return (
        f"Prepared with TenderShield · reviewed and approved on {meta.get('date', '')} "
        f"· pack {meta.get('pack', 'in-works')} · This is document-intelligence "
        f"software, not legal/QS advice — review with a qualified professional."
    )


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
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def render_docx(
    opportunity_title: str, artifacts: list[dict], findings: list[dict], meta: dict
) -> bytes:
    doc = Document()
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
