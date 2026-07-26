"""Page-level text chunks and the `ingestion.doc_text` capability (TS-068).

Text is split on `[pN]` page markers emitted by `extract.py`. If no markers are
present, the whole text is stored as page 1."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.ingestion.models import DocChunk

_PAGE_MARKER = re.compile(r"^\s*\[p(\d+)\]\s*$", re.MULTILINE)


@dataclass(frozen=True)
class PageChunk:
    page: int
    text: str


def extract_pages(text: str) -> list[PageChunk]:
    """Split a document body on `[pN]` markers into per-page chunks."""
    chunks: list[PageChunk] = []
    current: list[str] = []
    page = 1
    for line in text.splitlines():
        m = _PAGE_MARKER.match(line)
        if m:
            if current:
                chunks.append(PageChunk(page, "\n".join(current).strip()))
                current = []
            page = int(m.group(1))
            continue
        current.append(line)
    if current:
        chunks.append(PageChunk(page, "\n".join(current).strip()))
    if not chunks and text.strip():
        chunks.append(PageChunk(1, text.strip()))
    return sorted(chunks, key=lambda c: c.page)


def persist_chunks(
    session: Session, workspace_id, opportunity_id, document_id, text: str
) -> list[DocChunk]:
    """Replace existing doc_chunks for a document with the current extraction."""
    ws = uuid.UUID(str(workspace_id))
    opp = uuid.UUID(str(opportunity_id))
    doc = uuid.UUID(str(document_id))
    session.execute(delete(DocChunk).where(DocChunk.document_id == doc))
    rows = [
        DocChunk(
            workspace_id=ws,
            opportunity_id=opp,
            document_id=doc,
            page=chunk.page,
            text=chunk.text,
        )
        for chunk in extract_pages(text)
        if chunk.text
    ]
    session.add_all(rows)
    session.commit()
    return rows


class DocTextService:
    """Read-only page text access for cross-document search and assistants."""

    def __init__(self, session: Session):
        self.s = session

    def text_for_document(
        self, workspace_id, document_id, *, pages: Iterable[int] | None = None
    ) -> dict:
        """Return `{page: text}` for a document, optionally filtered to a page list."""
        stmt = (
            select(DocChunk)
            .where(
                DocChunk.document_id == uuid.UUID(str(document_id)),
                DocChunk.workspace_id == uuid.UUID(str(workspace_id)),
            )
            .order_by(DocChunk.page)
        )
        rows = list(self.s.scalars(stmt))
        result: dict[int, str] = {}
        if pages is not None:
            page_set = set(pages)
            for r in rows:
                if r.page in page_set:
                    result[r.page] = r.text
        else:
            for r in rows:
                result[r.page] = r.text
        return result

    def text_for_page(self, workspace_id, document_id, page: int) -> str | None:
        row = self.s.scalar(
            select(DocChunk).where(
                DocChunk.document_id == uuid.UUID(str(document_id)),
                DocChunk.workspace_id == uuid.UUID(str(workspace_id)),
                DocChunk.page == page,
            )
        )
        return row.text if row else None
