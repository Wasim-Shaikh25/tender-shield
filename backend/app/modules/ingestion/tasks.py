"""Celery tasks for async document processing (TS-034).

A task loads the uploaded file, extracts text page-by-page, persists chunks and
deadlines, and publishes progress that the SSE endpoint can stream.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from app.core.celery import make_celery_app
from app.core.config import Settings
from app.core.db import bind_workspace_context, make_engine, make_session_factory
from app.core.storage import StorageError, get_storage
from app.modules.ingestion.deadlines import extract_deadlines
from app.modules.ingestion.doc_text import persist_chunks
from app.modules.ingestion.extract import extract_upload
from app.modules.ingestion.models import Document

logger = logging.getLogger(__name__)
app = make_celery_app()


def _get_session(workspace_id: str):
    settings = Settings()
    engine = make_engine(settings)
    session_factory = make_session_factory(engine)
    session = session_factory()
    bind_workspace_context(session, workspace_id)
    return session


def _load_file(key: str):
    """Synchronous wrapper to read a stored file."""
    storage = get_storage(Settings())
    return asyncio.run(storage.read(key))


def _publish_progress(task, step: str, page: int, total: int):
    try:
        task.update_state(
            state="PROGRESS",
            meta={"step": step, "page": page, "total": total, "at": datetime.now(UTC).isoformat()},
        )
    except Exception:
        pass


@app.task(bind=True, name="ingestion.process_document")
def process_document(self, document_id: str, workspace_id: str, opportunity_id: str):
    """Async text extraction + deadline extraction for an uploaded document."""
    session = _get_session(workspace_id)
    try:
        doc = session.get(Document, uuid.UUID(document_id))
        if not doc:
            logger.warning("process_document: document %s not found", document_id)
            return {"status": "not_found"}

        if not doc.s3_key:
            return {"status": "no_storage_key"}

        _publish_progress(self, "loading", 0, 0)
        data = _load_file(doc.s3_key)

        _publish_progress(self, "extracting", 0, 0)
        text, ocr_status = extract_upload(doc.filename, data, ocr=None)

        pages = text.split("[p") if "[p" in text else [text]
        total = max(len(pages), 1)
        for i, _ in enumerate(pages, start=1):
            _publish_progress(self, "parsing", i, total)

        doc.ocr_status = ocr_status
        session.commit()

        persist_chunks(session, workspace_id, opportunity_id, document_id, text)

        # Extract deadlines from the full text and store them.
        for ex in extract_deadlines(text):
            from app.modules.ingestion.models import Deadline

            session.add(
                Deadline(
                    workspace_id=uuid.UUID(workspace_id),
                    opportunity_id=uuid.UUID(opportunity_id),
                    kind=ex.kind,
                    due_at=ex.due_at,
                    description=ex.description,
                    source_page=ex.source_page,
                    source_quote=ex.source_quote,
                )
            )
        session.commit()

        _publish_progress(self, "done", total, total)
        return {"status": "done", "chars": len(text), "pages": total, "ocr_status": ocr_status}
    except StorageError as exc:
        logger.exception("process_document storage error: %s", exc)
        return {"status": "storage_error", "reason": str(exc)}
    except Exception as exc:
        logger.exception("process_document failed: %s", exc)
        return {"status": "error", "reason": str(exc)}
    finally:
        session.close()
