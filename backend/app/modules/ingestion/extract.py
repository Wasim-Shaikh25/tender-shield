"""Text extraction from uploaded files (Doc §6.1). Digital PDFs via pypdf,
spreadsheets via openpyxl, CSV/text directly. Page markers ([pN]) are emitted
so downstream deadline/clause extraction can cite pages. Scanned-PDF OCR
(Textract) is TS-033."""

from __future__ import annotations

import csv
import io


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return _pdf(data)
    if name.endswith((".xlsx", ".xlsm")):
        return _xlsx(data)
    if name.endswith((".csv", ".txt", ".md")):
        return data.decode("utf-8", errors="replace")
    # Unknown type: best-effort decode.
    return data.decode("utf-8", errors="replace")


def looks_like_boq_csv(filename: str, data: bytes) -> bool:
    name = filename.lower()
    if not name.endswith(".csv"):
        return False
    header = data[:200].decode("utf-8", errors="replace").lower()
    return "description" in header and ("qty" in header or "rate" in header)


def _pdf(data: bytes) -> str:
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(data))
    return "\n".join(
        f"[p{i + 1}]\n{(page.extract_text() or '')}" for i, page in enumerate(reader.pages)
    )


def _xlsx(data: bytes) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    lines: list[str] = []
    for ws in wb.worksheets:
        lines.append(f"[sheet:{ws.title}]")
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                lines.append("\t".join(cells))
    return "\n".join(lines)


def xlsx_to_csv(data: bytes) -> str:
    """First sheet → CSV text, for the BOQ engine (which reads a workbook)."""
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in ws.iter_rows(values_only=True):
        writer.writerow(["" if c is None else c for c in row])
    return buf.getvalue()
