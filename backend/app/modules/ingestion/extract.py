"""Text extraction from uploaded files (Doc §6.1). Digital PDFs via pypdf,
spreadsheets via openpyxl, CSV/text directly. Page markers ([pN]) are emitted
so downstream deadline/clause extraction can cite pages. Scanned/image PDFs are
routed to an injected OCR provider (app/modules/ingestion/ocr.py); with none,
they are flagged `needs_ocr` and degrade honestly (Doc §12.4)."""

from __future__ import annotations

import io

_MIN_PAGE_CHARS = 10  # a page with less digital text than this is "empty"


def extract_text(filename: str, data: bytes) -> str:
    """Simple digital-only extraction (no OCR). Kept for callers that pass text."""
    name = filename.lower()
    if name.endswith(".pdf"):
        return _pdf(data)
    if name.endswith((".xlsx", ".xlsm")):
        return _xlsx(data)
    if name.endswith(".csv"):
        return _csv(data)
    if name.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="replace")
    return data.decode("utf-8", errors="replace")


def _join_pages(pages: list[str]) -> str:
    return "\n".join(f"[p{i + 1}]\n{p}" for i, p in enumerate(pages))


def _pdf_pages(data: bytes) -> list[str]:
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(data))
    return [(page.extract_text() or "") for page in reader.pages]


def extract_upload(filename: str, data: bytes, ocr=None) -> tuple[str, str]:
    """Extraction for uploads. Returns (text, ocr_status) where ocr_status is
    one of: done | ocr_applied | needs_ocr. PDFs with no digital text layer are
    OCR'd when a provider is given, else flagged needs_ocr."""
    name = filename.lower()
    if not name.endswith(".pdf"):
        return extract_text(filename, data), "done"

    pages = _pdf_pages(data)
    has_text = any(len(p.strip()) >= _MIN_PAGE_CHARS for p in pages)
    if pages and not has_text:
        if ocr is not None and getattr(ocr, "name", "null") != "null":
            return _join_pages(ocr.ocr_pdf(data)), "ocr_applied"
        return _join_pages(pages), "needs_ocr"
    return _join_pages(pages), "done"


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
        for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
            cells = [str(c) for c in row if c is not None]
            if cells:
                lines.append(f"[p{row_idx}]")
                lines.append("\t".join(cells))
    return "\n".join(lines)


def _csv(data: bytes) -> str:
    text = data.decode("utf-8", errors="replace")
    lines: list[str] = []
    for row_idx, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            lines.append(f"[p{row_idx}]")
            lines.append(line)
    return "\n".join(lines)


def xlsx_to_rows(data: bytes) -> list[list[str]] | None:
    """First sheet → list of row lists, for BOQ canonical CSV conversion."""
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows: list[list[str]] = []
    for row in ws.iter_rows(values_only=True):
        cells = ["" if c is None else str(c) for c in row]
        if any(cells):
            rows.append(cells)
    return rows if rows else None
