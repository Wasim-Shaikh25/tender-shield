"""Page-level text chunks and the `ingestion.doc_text` capability (TS-068).

Text is split on `[pN]` page markers emitted by `extract.py`. If no markers are
present, the whole text is stored as page 1.

Language detection is script-based and lightweight (no external NLP library).
When an OpenRouter key is configured, a short English summary/translation of
non-English content is produced on demand and stored in document metadata; the
original text is never replaced (TS-315).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.ingestion.models import DocChunk

_PAGE_MARKER = re.compile(r"^\s*\[p(\d+)\]\s*$", re.MULTILINE)

# Lightweight script-based language detection for Indian + major non-Latin scripts.
_SCRIPT_RANGES = [
    ("hi", r"[\u0900-\u097F]"),  # Devanagari
    ("bn", r"[\u0980-\u09FF]"),  # Bengali
    ("te", r"[\u0C00-\u0C7F]"),  # Telugu
    ("ta", r"[\u0B80-\u0BFF]"),  # Tamil
    ("ml", r"[\u0D00-\u0D7F]"),  # Malayalam
    ("kn", r"[\u0C80-\u0CFF]"),  # Kannada
    ("gu", r"[\u0A80-\u0AFF]"),  # Gujarati
    ("pa", r"[\u0A00-\u0A7F]"),  # Gurmukhi
    ("or", r"[\u0B00-\u0B7F]"),  # Oriya
    ("ar", r"[\u0600-\u06FF\u0750-\u077F]"),  # Arabic
    ("zh", r"[\u4E00-\u9FFF]"),  # CJK
    ("ja", r"[\u3040-\u309F\u30A0-\u30FF]"),  # Hiragana/Katakana
    ("ko", r"[\uAC00-\uD7AF]"),  # Hangul
    ("ru", r"[\u0400-\u04FF]"),  # Cyrillic
]


def detect_language(text: str) -> str:
    """Return a BCP-47-ish language code from script ranges. Falls back to `en`."""
    if not text:
        return "en"
    sample = text[:5000]
    counts: dict[str, int] = {}
    for lang, pattern in _SCRIPT_RANGES:
        counts[lang] = len(re.findall(pattern, sample))
    if not any(counts.values()):
        # No non-Latin script detected; assume English/latin-script.
        return "en"
    return max(counts, key=lambda k: counts[k])


def translate_summary(text: str, source_language: str, client: Any | None = None) -> str | None:
    """Return a short English summary/translation of non-English text.

    The original text is preserved; this only produces a metadata helper. If no
    LLM client is available or the source language is English, returns None.
    """
    if source_language == "en" or not text or client is None:
        return None
    snippet = text[:2000].strip()
    if not snippet:
        return None
    system = (
        "You are a translation assistant for tender documents. "
        "Translate and briefly summarize the user's non-English text into English. "
        "Keep the summary concise (max 3 sentences) and preserve all named entities, "
        "dates, and numbers exactly as written."
    )
    user = f"<source language=\"{source_language}\">\n{snippet}\n</source>"
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=300,
            temperature=0.0,
        )
        summary = response.choices[0].message.content.strip()
        return summary or None
    except Exception:
        return None


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
