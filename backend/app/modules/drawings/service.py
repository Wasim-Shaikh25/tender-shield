"""DrawingService — register, title-block extraction, revision control,
region-level text comparison, symbol assist, BOQ links, and heatmaps
(TS-321–TS-325).

Soft dependencies on `ingestion` via the registry for text/OCR extraction.
"""

from __future__ import annotations

import difflib
import io
import re
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.drawings import heatmap, ifc, vision
from app.modules.drawings.models import Drawing, DrawingBoqLink, DrawingComparison


class DrawingsError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# Title-block fields we try to pull from the first pages of text.
_TITLE_BLOCK_PATTERNS = {
    "drawing_number": re.compile(
        r"(?:drawing\s*no|drg|drawing)[.\s]*[:\-]?\s*"
        r"([A-Z0-9\-/]{3,50})(?=[^A-Za-z0-9\-/]|$)",
        re.IGNORECASE,
    ),
    "title": re.compile(
        r"(?:title|name|description)[.\s]*[:\-]?\s*"
        r"([A-Z][^\n]{2,120})(?=\n|$)",
        re.IGNORECASE,
    ),
    "revision": re.compile(
        r"(?:revision|rev)[.\s]*[:\-]?\s*([A-Z0-9]{1,10})(?=[^A-Za-z0-9]|$)",
        re.IGNORECASE,
    ),
    "revision_date": re.compile(
        r"(?:date|revision\s*date)[.\s]*[:\-]?\s*"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})(?=\s|$)",
        re.IGNORECASE,
    ),
    "discipline": re.compile(
        r"(?:discipline|trade)[.\s]*[:\-]?\s*([A-Za-z]{3,30})(?=[^A-Za-z]|$)",
        re.IGNORECASE,
    ),
}


def _extract_title_block(text: str) -> dict:
    """Pull title-block fields from the first 4000 characters of extracted text."""
    sample = text[:4000]
    return {
        key: (m.group(1).strip() if (m := pat.search(sample)) else None)
        for key, pat in _TITLE_BLOCK_PATTERNS.items()
    }


def _split_pages(text: str) -> list[str]:
    """Split extracted text into pages using [pN] markers, falling back to newlines."""
    pages = re.split(r"\n\s*\[p(\d+)\]\s*\n", text)
    if len(pages) > 1:
        return [p for p in pages if not p.strip().isdigit()]
    return text.split("\n\f") if "\f" in text else text.splitlines()


def _page_regions(page_text: str) -> list[dict]:
    """Break a page into coarse regions (header/body/footer) by line count."""
    lines = [line for line in page_text.splitlines() if line.strip()]
    if not lines:
        return []
    n = len(lines)
    header_end = max(1, n // 6)
    body_end = max(2, n * 5 // 6)
    return [
        {
            "name": "header",
            "start_line": 0,
            "end_line": header_end,
            "line_count": header_end,
        },
        {
            "name": "body",
            "start_line": header_end,
            "end_line": body_end,
            "line_count": body_end - header_end,
        },
        {
            "name": "footer",
            "start_line": body_end,
            "end_line": n,
            "line_count": n - body_end,
        },
    ]


def _pdf_text(data: bytes) -> str:
    """Extract text from a PDF using pdfplumber. Falls back to empty string."""
    try:
        import pdfplumber
    except ImportError:
        return ""
    parts: list[str] = []
    with io.BytesIO(data) as bio:
        try:
            with pdfplumber.open(bio) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    txt = page.extract_text() or ""
                    parts.append(f"[p{i}]\n{txt}")
        except Exception:
            return ""
    return "\n\n".join(parts)


def _ocr_text(data: bytes, filename: str, ocr_provider: Any) -> str:
    if ocr_provider is None:
        return ""
    try:
        if filename.lower().endswith(".pdf"):
            # RapidOcrProvider typically expects images; degrade gracefully.
            return ""
        return ocr_provider.ocr_image(data) or ""
    except Exception:
        return ""


class DrawingService:
    def __init__(
        self,
        session: Session,
        *,
        ocr_provider: Any | None = None,
        extract_pdf: Callable[[bytes], str] | None = None,
    ):
        self.s = session
        self._ocr_provider = ocr_provider
        self._extract_pdf = extract_pdf or _pdf_text

    def _ws_uuid(self, value) -> uuid.UUID:
        return uuid.UUID(str(value))

    def create(
        self,
        workspace_id,
        opportunity_id,
        *,
        filename: str,
        document_id: str | None = None,
        file_data: bytes | None = None,
        drawing_number: str | None = None,
        title: str | None = None,
        revision: str | None = None,
        revision_date: str | None = None,
        discipline: str | None = None,
        supersedes_id: str | None = None,
    ) -> Drawing:
        extracted = ""
        page_count = None
        if file_data:
            if filename.lower().endswith(".pdf"):
                extracted = self._extract_pdf(file_data)
                page_count = extracted.count("[p")
            else:
                extracted = _ocr_text(file_data, filename, self._ocr_provider)

        title_block = _extract_title_block(extracted)
        if drawing_number:
            title_block["drawing_number"] = drawing_number
        if title:
            title_block["title"] = title
        if revision:
            title_block["revision"] = revision
        if revision_date:
            title_block["revision_date"] = revision_date
        if discipline:
            title_block["discipline"] = discipline

        row = Drawing(
            workspace_id=self._ws_uuid(workspace_id),
            opportunity_id=self._ws_uuid(opportunity_id),
            document_id=self._ws_uuid(document_id) if document_id else None,
            filename=filename,
            drawing_number=title_block.get("drawing_number") or drawing_number,
            title=title_block.get("title") or title,
            revision=title_block.get("revision") or revision,
            revision_date=title_block.get("revision_date") or revision_date,
            discipline=title_block.get("discipline") or discipline,
            supersedes_id=self._ws_uuid(supersedes_id) if supersedes_id else None,
            page_count=page_count,
            extracted_text=extracted,
            title_block=title_block,
            status="current",
        )
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        return row

    def list(self, workspace_id, opportunity_id) -> list[Drawing]:
        return list(
            self.s.scalars(
                select(Drawing).where(
                    Drawing.workspace_id == self._ws_uuid(workspace_id),
                    Drawing.opportunity_id == self._ws_uuid(opportunity_id),
                ).order_by(Drawing.drawing_number, Drawing.revision)
            )
        )

    def get(self, workspace_id, drawing_id) -> Drawing | None:
        return self.s.scalar(
            select(Drawing).where(
                Drawing.workspace_id == self._ws_uuid(workspace_id),
                Drawing.id == self._ws_uuid(drawing_id),
            )
        )

    def update_extraction(
        self, workspace_id, drawing_id, file_data: bytes, filename: str | None = None
    ) -> Drawing:
        row = self.get(workspace_id, drawing_id)
        if not row:
            raise DrawingsError("drawing_not_found")
        extracted = ""
        page_count = None
        name = filename or row.filename
        if file_data:
            if name.lower().endswith(".pdf"):
                extracted = self._extract_pdf(file_data)
                page_count = extracted.count("[p")
            else:
                extracted = _ocr_text(file_data, name, self._ocr_provider)
        row.extracted_text = extracted
        row.page_count = page_count
        title_block = _extract_title_block(extracted)
        for key in (
            "drawing_number",
            "title",
            "revision",
            "revision_date",
            "discipline",
        ):
            if title_block.get(key) and not getattr(row, key):
                setattr(row, key, title_block[key])
        row.title_block = {**row.title_block, **{k: v for k, v in title_block.items() if v}}
        self.s.commit()
        self.s.refresh(row)
        return row

    def supersede(self, workspace_id, current_id, previous_id) -> Drawing:
        current = self.get(workspace_id, current_id)
        previous = self.get(workspace_id, previous_id)
        if not current or not previous:
            raise DrawingsError("drawing_not_found")
        current.supersedes_id = previous.id
        current.status = "current"
        previous.status = "superseded"
        self.s.commit()
        self.s.refresh(current)
        return current

    def compare(
        self,
        workspace_id,
        current_id: str,
        previous_id: str,
    ) -> DrawingComparison:
        current = self.get(workspace_id, current_id)
        previous = self.get(workspace_id, previous_id)
        if not current or not previous:
            raise DrawingsError("drawing_not_found")

        cur_pages = _split_pages(current.extracted_text or "")
        prev_pages = _split_pages(previous.extracted_text or "")

        changed_pages: list[int] = []
        changed_regions: list[dict] = []
        max_pages = max(len(cur_pages), len(prev_pages))
        for i in range(max_pages):
            cur = cur_pages[i] if i < len(cur_pages) else ""
            prev = prev_pages[i] if i < len(prev_pages) else ""
            if cur != prev:
                changed_pages.append(i + 1)
                cur_regions = _page_regions(cur)
                prev_regions = _page_regions(prev)
                for r_cur, r_prev in zip(cur_regions, prev_regions, strict=False):
                    cur_lines = cur.splitlines()[r_cur["start_line"]:r_cur["end_line"]]
                    prev_lines = prev.splitlines()[r_prev["start_line"]:r_prev["end_line"]]
                    cur_text = "\n".join(cur_lines)
                    prev_text = "\n".join(prev_lines)
                    if cur_text != prev_text:
                        diff = list(
                            difflib.unified_diff(
                                prev_lines, cur_lines, lineterm=""
                            )
                        )

                        def _is_add(line: str) -> bool:
                            return line.startswith("+") and not line.startswith("+++")

                        def _is_rem(line: str) -> bool:
                            return line.startswith("-") and not line.startswith("---")

                        changed_regions.append(
                            {
                                "page": i + 1,
                                "region": r_cur["name"],
                                "lines_added": sum(1 for d in diff if _is_add(d)),
                                "lines_removed": sum(1 for d in diff if _is_rem(d)),
                            }
                        )

        summary = (
            f"{len(changed_pages)} of {max_pages} page(s) changed; "
            f"{len(changed_regions)} region(s) differ."
        )
        comp = DrawingComparison(
            workspace_id=self._ws_uuid(workspace_id),
            opportunity_id=current.opportunity_id,
            current_drawing_id=current.id,
            previous_drawing_id=previous.id,
            summary=summary,
            changed_pages=changed_pages,
            changed_regions=changed_regions,
        )
        self.s.add(comp)
        self.s.commit()
        self.s.refresh(comp)
        return comp

    def symbol_assist(self, workspace_id, drawing_id: str) -> dict:
        row = self.get(workspace_id, drawing_id)
        if not row:
            raise DrawingsError("drawing_not_found")
        result = vision.symbol_assist(row.extracted_text)
        row.symbol_suggestions = result
        self.s.commit()
        return result

    def link_boq(
        self,
        workspace_id,
        opportunity_id,
        drawing_id: str,
        *,
        page: int | None = None,
        region: str | None = None,
        source_quote: str | None = None,
        item_code: str | None = None,
        description: str = "",
        unit: str = "",
        qty: float | None = None,
        rate_minor: int | None = None,
        currency: str = "INR",
    ) -> DrawingBoqLink:
        row = self.get(workspace_id, drawing_id)
        if not row:
            raise DrawingsError("drawing_not_found")
        link = DrawingBoqLink(
            workspace_id=self._ws_uuid(workspace_id),
            opportunity_id=self._ws_uuid(opportunity_id),
            drawing_id=row.id,
            page=page,
            region=region,
            source_quote=source_quote,
            item_code=item_code,
            description=description,
            unit=unit,
            qty=qty,
            rate_minor=rate_minor,
            currency=currency,
        )
        self.s.add(link)
        self.s.commit()
        self.s.refresh(link)
        return link

    def list_boq_links(self, workspace_id, opportunity_id) -> list[DrawingBoqLink]:
        return list(
            self.s.scalars(
                select(DrawingBoqLink).where(
                    DrawingBoqLink.workspace_id == self._ws_uuid(workspace_id),
                    DrawingBoqLink.opportunity_id == self._ws_uuid(opportunity_id),
                ).order_by(DrawingBoqLink.created_at)
            )
        )

    def heatmap(self, workspace_id, drawing_id: str) -> dict:
        row = self.get(workspace_id, drawing_id)
        if not row:
            raise DrawingsError("drawing_not_found")
        result = heatmap.confidence_heatmap(
            row.extracted_text,
            row.title_block or {},
            row.symbol_suggestions,
        )
        row.heatmap = result
        self.s.commit()
        return result

    def ifc_quantities(self, workspace_id, drawing_id: str, file_data: bytes) -> dict:
        row = self.get(workspace_id, drawing_id)
        if not row:
            raise DrawingsError("drawing_not_found")
        try:
            text = file_data.decode("utf-8", errors="ignore")
        except Exception as exc:
            raise DrawingsError("ifc_decode_failed") from exc
        return ifc.extract_ifc_quantities(text)
