"""PDF table extraction (Doc §6.1) — pdfplumber, no cloud. Reads tables out of
DIGITAL PDFs so a BOQ embedded as a PDF table can feed the deterministic BOQ
engine without a manual CSV/XLSX. (Scanned-image BOQ table reconstruction is
the genuinely hard case — needs OCR + layout analysis, a follow-up.)"""

from __future__ import annotations

import csv
import io
from html.parser import HTMLParser

# Header aliases → the canonical BOQ columns the engine expects.
_HEADER_ALIASES = {
    "src_row": ["s.no", "sno", "sr", "item no", "srno", "row"],
    "item_code": ["item code", "code", "item"],
    "description": ["description", "particular", "particulars", "item description"],
    "unit_raw": ["unit", "uom"],
    "qty": ["qty", "quantity", "quantum"],
    "rate": ["rate", "unit rate"],
    "amount": ["amount", "value", "total"],
}


def extract_tables(pdf_bytes: bytes) -> list[list[list[str]]]:
    """Return each detected table as a list of rows (list of cell strings)."""
    import pdfplumber

    tables: list[list[list[str]]] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            for tbl in page.extract_tables():
                cleaned = [[(c or "").strip() for c in row] for row in tbl if any(row)]
                if cleaned:
                    tables.append(cleaned)
    return tables


def _map_header(cell: str) -> str | None:
    c = cell.strip().lower()
    for canon, aliases in _HEADER_ALIASES.items():
        if c == canon or c in aliases:
            return canon
    return None


def find_boq_table(tables: list[list[list[str]]]) -> list[list[str]] | None:
    """Pick the table whose header row maps to the most BOQ columns (needs at
    least description + one of qty/rate/amount)."""
    best, best_score = None, 0
    for tbl in tables:
        header = tbl[0]
        mapped = {_map_header(c) for c in header} - {None}
        score = len(mapped)
        if "description" in mapped and mapped & {"qty", "rate", "amount"} and score > best_score:
            best, best_score = tbl, score
    return best


def boq_table_to_csv(table: list[list[str]]) -> str:
    """Rewrite a detected BOQ table to canonical-header CSV for the BOQ engine."""
    header = [(_map_header(c) or c.strip().lower().replace(" ", "_")) for c in table[0]]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in table[1:]:
        writer.writerow(row)
    return buf.getvalue()


class _HtmlTable(HTMLParser):
    """Minimal <table> → rows parser (no external deps) for OCR'd table HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def html_table_to_rows(html: str) -> list[list[str]]:
    parser = _HtmlTable()
    parser.feed(html or "")
    return parser.rows


def scanned_boq_csv(table_html_pages: list[str]) -> str | None:
    """Turn OCR'd table HTML (one per page) into canonical BOQ CSV, if any page
    yields a BOQ-shaped table."""
    tables = [rows for html in table_html_pages if (rows := html_table_to_rows(html))]
    boq = find_boq_table(tables)
    return boq_table_to_csv(boq) if boq else None


def file_to_boq_csv(filename: str, data: bytes) -> str | None:
    """Turn an uploaded BOQ file into canonical CSV for the engine. CSV as-is,
    XLSX via openpyxl, PDF via table detection. Published as a capability so the
    BOQ module reads workbooks without importing ingestion."""
    from app.modules.ingestion.extract import xlsx_to_csv

    name = filename.lower()
    if name.endswith(".csv"):
        return data.decode("utf-8", errors="replace")
    if name.endswith((".xlsx", ".xlsm")):
        return xlsx_to_csv(data)
    if name.endswith(".pdf"):
        table = find_boq_table(extract_tables(data))
        return boq_table_to_csv(table) if table else None
    return None
