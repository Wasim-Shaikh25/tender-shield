"""Celery tasks for async document processing (TS-034).

A task loads the uploaded file, extracts text page-by-page, persists chunks and
deadlines, and publishes progress that the SSE endpoint can stream.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime

from app.core.celery import make_celery_app
from app.core.config import Settings
from app.core.costmeter import record_worker_seconds, review_cost_scope
from app.core.db import bind_workspace_context, make_engine, make_session_factory
from app.core.storage import StorageError, get_storage
from app.modules.ingestion.extract import extract_upload
from app.modules.ingestion.models import Document
from app.modules.ingestion.ocr import NullOcrProvider, RapidOcrProvider
from app.modules.ingestion.service import IngestionService

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


def _get_ocr():
    settings = Settings()
    return RapidOcrProvider() if settings.ocr_enabled else NullOcrProvider()


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
    """Async text extraction, classification, segmentation, deadlines, and OCR."""
    session = _get_session(workspace_id)
    started = time.monotonic()
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
        ocr = _get_ocr()
        # Meter the whole extraction pipeline as one unit of review work (TS-223).
        with review_cost_scope(opportunity_id=opportunity_id):
            text, ocr_status = extract_upload(doc.filename, data, ocr=ocr)

            pages = text.split("[p") if "[p" in text else [text]
            total = max(len(pages), 1)
            for i, _ in enumerate(pages, start=1):
                _publish_progress(self, "parsing", i, total)

            # Re-classify, segment clauses, extract deadlines, persist chunks, and update
            # the opportunity submission_due using the same service logic as the sync path.
            svc = IngestionService(session, loader_provider=None)
            svc.process_text(doc, text, ocr_status=ocr_status)
            record_worker_seconds(time.monotonic() - started)

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
