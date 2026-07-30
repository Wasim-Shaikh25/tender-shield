"""TenderShield Office MCP server.

Exposes tools for QS engineers to read and update Microsoft Word/Excel tender
documents from an LLM client (Claude Desktop, Cursor, etc.) that speaks the
Model Context Protocol (MCP).

Transport: stdio (default). Start with:

    python -m tendershield_office_mcp.server

or install as a package and run:

    python -m tendershield_office_mcp
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from openpyxl import Workbook, load_workbook

try:
    from docx import Document
except ImportError:  # pragma: no cover - guard for typing in minimal envs
    Document = None  # type: ignore[assignment,misc]

mcp = FastMCP("tendershield-office")


def _resolve_path(path: str) -> Path:
    """Reject parent-directory traversal and expand user paths."""
    p = Path(path).expanduser().resolve()
    cwd = Path(os.getcwd()).resolve()
    if not str(p).startswith(str(cwd)):
        raise ValueError("path must be inside the current working directory")
    return p


def _load_docx(path: Path) -> Any:
    if Document is None:
        raise RuntimeError("python-docx is not installed")
    return Document(str(path))


@mcp.tool()
def read_word_document(path: str) -> str:
    """Read the text and tables of a Microsoft Word (.docx) tender document."""
    p = _resolve_path(path)
    if not p.exists():
        return f"File not found: {p}"
    doc = _load_docx(p)
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    tables: list[list[list[str]]] = []
    for table in doc.tables:
        rows = []
        for row in table.rows:
            rows.append([cell.text for cell in row.cells])
        tables.append(rows)
    return json.dumps({"paragraphs": paragraphs, "tables": tables}, indent=2)


@mcp.tool()
def read_excel_workbook(path: str, sheet: str | None = None, max_rows: int = 100) -> str:
    """Read an Excel workbook (or a single sheet) as JSON."""
    p = _resolve_path(path)
    if not p.exists():
        return f"File not found: {p}"
    wb = load_workbook(str(p), data_only=True)
    if sheet:
        sheets = [wb[sheet]]
    else:
        sheets = wb.worksheets
    output: dict[str, list[list[Any]]] = {}
    for ws in sheets:
        rows = []
        for row in ws.iter_rows(values_only=True, max_row=max_rows):
            rows.append([str(v) if v is not None else "" for v in row])
        output[ws.title] = rows
    return json.dumps(output, indent=2)


@mcp.tool()
def write_word_comments(path: str, comments: list[str], heading: str = "TenderShield Review Comments") -> str:
    """Append a section of review comments to an existing Word document."""
    p = _resolve_path(path)
    if not p.exists():
        return f"File not found: {p}"
    doc = _load_docx(p)
    doc.add_heading(heading, level=1)
    for comment in comments:
        doc.add_paragraph(comment, style="List Bullet")
    doc.save(str(p))
    return f"Saved {len(comments)} comments to {p}"


@mcp.tool()
def create_summary_doc(path: str, title: str, sections: list[dict[str, Any]]) -> str:
    """Create a new Word document summarizing tender review findings.

    sections: list of {"heading": str, "items": [str]}
    """
    p = _resolve_path(path)
    if p.exists():
        return f"File already exists: {p}"
    doc = _load_docx_with_new()
    doc.add_heading(title, level=0)
    for section in sections:
        heading = section.get("heading", "Section")
        items = section.get("items", []) or []
        doc.add_heading(heading, level=1)
        for item in items:
            doc.add_paragraph(str(item), style="List Bullet")
    doc.save(str(p))
    return f"Created {p}"


@mcp.tool()
def append_excel_rows(path: str, sheet: str, rows: list[list[Any]]) -> str:
    """Append rows to an Excel worksheet, creating the workbook/sheet if missing."""
    p = _resolve_path(path)
    if p.exists():
        wb = load_workbook(str(p))
        if sheet in wb.sheetnames:
            ws = wb[sheet]
        else:
            ws = wb.create_sheet(title=sheet)
    else:
        wb = Workbook()
        ws = wb.active
        if ws is None:
            ws = wb.create_sheet()
        ws.title = sheet
    for row in rows:
        ws.append([str(v) if v is not None else "" for v in row])
    wb.save(str(p))
    return f"Appended {len(rows)} rows to {p}::{sheet}"


def _load_docx_with_new() -> Any:
    if Document is None:
        raise RuntimeError("python-docx is not installed")
    return Document()


if __name__ == "__main__":
    mcp.run()
