import asyncio
import pathlib
import time
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.core.pagination import PaginationParams, paginated_list_response
from app.core.storage import (
    DEFAULT_MAX_UPLOAD_SIZE,
    MAX_UPLOAD_SIZES,
    StorageError,
    ValidationError,
    validate_and_store,
)
from app.modules.ingestion import tus
from app.modules.ingestion.extract import extract_upload
from app.modules.ingestion.service import IngestionService
from app.modules.ingestion.tasks import process_document

router = APIRouter()
router.include_router(tus.router)


def _service(request: Request, session: Session) -> IngestionService:
    reg = request.app.state.ctx.registry
    return IngestionService(
        session,
        loader_provider=lambda: reg.get("rulepacks.loader"),
        publish=request.app.state.ctx.events.publish,
    )


class CreateOpportunityBody(BaseModel):
    title: str = Field(min_length=1)
    employer: str | None = None
    employer_family: str | None = None
    jurisdiction: str = "IN"
    contract_value_minor: int | None = Field(default=None, ge=0)
    currency: str = "INR"


class RegisterDocumentBody(BaseModel):
    filename: str = Field(min_length=1)
    sample_text: str = Field(default="", max_length=1_000_000)
    supersedes: str | None = None


@router.get("/opportunities")
def list_opportunities(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    page: PaginationParams = Depends(),
):
    opps = _service(request, session).list_opportunities(principal.workspace_id)
    items = [_opp_json(o) for o in opps]
    return {"opportunities": paginated_list_response(items, page, response)}


def _opp_json(o) -> dict:
    return {
        "id": str(o.id),
        "title": o.title,
        "status": o.status,
        "contract_value_minor": o.contract_value_minor,
        "currency": o.currency,
        "submission_due": o.submission_due.isoformat() if o.submission_due else None,
    }


@router.post("/opportunities")
def create_opportunity(
    body: CreateOpportunityBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    opp = _service(request, session).create_opportunity(
        principal.workspace_id,
        body.title,
        employer=body.employer,
        employer_family=body.employer_family,
        jurisdiction=body.jurisdiction,
        contract_value_minor=body.contract_value_minor,
        currency=body.currency,
    )
    return _opp_json(opp)


@router.get("/opportunities/{opportunity_id}")
def get_opportunity(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    opp = _service(request, session).get_opportunity(principal.workspace_id, opportunity_id)
    if not opp:
        raise HTTPException(404, "not_found")
    return _opp_json(opp)


@router.post("/opportunities/{opportunity_id}/documents")
def register_document(
    opportunity_id: str,
    body: RegisterDocumentBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    svc = _service(request, session)
    if not svc.get_opportunity(principal.workspace_id, opportunity_id):
        raise HTTPException(404, "not_found")
    doc = svc.register_document(
        principal.workspace_id,
        opportunity_id,
        body.filename,
        body.sample_text,
        uploaded_by=_to_uuid(principal.user_id),
        supersedes=_to_uuid(body.supersedes),
    )
    return {"id": str(doc.id), "filename": doc.filename, "kind": doc.kind}


@router.post("/opportunities/{opportunity_id}/upload")
async def upload_document(
    opportunity_id: str,
    request: Request,
    file: UploadFile = File(...),
    async_process: bool = Query(False, alias="async"),
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    """Real multipart upload → store file → extract text (PDF/XLSX/CSV) → run the
    classify/segment/deadline pipeline. Set ?async=1 to enqueue Celery processing
    and stream progress via the SSE endpoint."""
    svc = _service(request, session)
    if not svc.get_opportunity(principal.workspace_id, opportunity_id):
        raise HTTPException(404, "not_found")

    ext = pathlib.Path(file.filename or "").suffix.lower()
    max_size = MAX_UPLOAD_SIZES.get(ext, DEFAULT_MAX_UPLOAD_SIZE)
    data = await file.read(max_size + 1)
    if len(data) > max_size:
        raise HTTPException(413, "upload_too_large")

    try:
        stored = await validate_and_store(
            request.app.state.ctx.settings,
            file.filename,
            file.content_type,
            data,
            max_size=max_size,
            workspace_id=str(principal.workspace_id),
        )
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(500, str(exc)) from exc

    if async_process:
        doc = svc.register_document(
            principal.workspace_id,
            opportunity_id,
            file.filename,
            "",
            s3_key=stored["key"],
            sha256=stored["sha256"],
            ocr_status="pending",
            uploaded_by=_to_uuid(principal.user_id),
        )
        task = process_document.delay(
            str(doc.id), str(principal.workspace_id), opportunity_id
        )
        return {
            "id": str(doc.id),
            "filename": doc.filename,
            "kind": doc.kind,
            "task_id": task.id,
            "ocr_status": "pending",
        }

    ocr = request.app.state.ctx.registry.get("ingestion.ocr")
    # `extract_upload` may parse PDF/CSV/XLSX and run OCR; keep it out of the
    # async event loop by running in the default executor.
    text, ocr_status = await asyncio.to_thread(extract_upload, file.filename, data, ocr)
    doc = svc.register_document(
        principal.workspace_id,
        opportunity_id,
        file.filename,
        text,
        s3_key=stored["key"],
        sha256=stored["sha256"],
        ocr_status=ocr_status,
        uploaded_by=_to_uuid(principal.user_id),
    )
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "kind": doc.kind,
        "chars": len(text),
        "ocr_status": ocr_status,
    }


@router.get("/opportunities/{opportunity_id}/documents/{document_id}/stream")
async def document_stream(
    opportunity_id: str,
    document_id: str,
    task_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    """Server-Sent Events stream of a Celery document-processing task."""
    from celery.result import AsyncResult

    svc = _service(request, session)
    if not svc.get_document(principal.workspace_id, document_id):
        raise HTTPException(404, "not_found")

    async def _events():
        app = request.app.state.ctx.registry.get("celery.app")
        if not app:
            yield _sse_event("error", "celery not configured")
            return
        result = AsyncResult(task_id, app=app)
        prev = {}
        started = time.monotonic()
        while not result.ready():
            if await request.is_disconnected():
                return
            if time.monotonic() - started > 600:
                yield _sse_event("error", "timeout")
                return
            meta = result.info or {}
            if meta != prev:
                prev = meta.copy()
                yield _sse_event(meta.get("step", "progress"), meta)
            await asyncio.sleep(0.5)
        if result.successful():
            yield _sse_event("done", result.result)
        else:
            yield _sse_event("error", str(result.result))

    return StreamingResponse(_events(), media_type="text/event-stream")


def _sse_event(event: str, data):
    import json
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.get("/opportunities/{opportunity_id}/clauses")
def list_clauses(
    opportunity_id: str,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    page: PaginationParams = Depends(),
):
    clauses = _service(request, session).list_clauses(principal.workspace_id, opportunity_id)
    items = [
        {
            "id": str(c.id),
            "clause_ref": c.clause_ref,
            "heading": c.heading,
            "page_from": c.page_from,
            "cross_refs": c.cross_refs,
        }
        for c in clauses
    ]
    return {"clauses": paginated_list_response(items, page, response)}


@router.get("/opportunities/{opportunity_id}/deadlines")
def list_deadlines(
    opportunity_id: str,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    page: PaginationParams = Depends(),
):
    deadlines = _service(request, session).list_deadlines(principal.workspace_id, opportunity_id)
    items = [
        {
            "id": str(d.id),
            "kind": d.kind,
            "due_at": d.due_at.isoformat() if d.due_at else None,
            "description": d.description,
            "source_page": d.source_page,
            "source_quote": d.source_quote,
            "confirmed": d.confirmed,
        }
        for d in deadlines
    ]
    return {"deadlines": paginated_list_response(items, page, response)}


@router.post("/opportunities/{opportunity_id}/deadlines/{deadline_id}/confirm")
def confirm_deadline(
    opportunity_id: str,
    deadline_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    dl = _service(request, session).confirm_deadline(
        principal.workspace_id, opportunity_id, deadline_id
    )
    if not dl:
        raise HTTPException(404, "not_found")
    return {"id": str(dl.id), "confirmed": dl.confirmed}


@router.get("/opportunities/{opportunity_id}/missing-docs")
def missing_docs(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).missing_doc_report(principal.workspace_id, opportunity_id)


@router.get("/documents/{document_id}/text")
def get_document_text(
    document_id: str,
    page: int | None = None,
    request: Request = None,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).get_doc_text(principal.workspace_id, document_id, page=page)


@router.get("/opportunities/{opportunity_id}/documents/{document_id}/addendum")
def get_addendum(
    opportunity_id: str,
    document_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    svc = _service(request, session)
    doc = svc.get_document(principal.workspace_id, document_id)
    if not doc or str(doc.opportunity_id) != opportunity_id:
        raise HTTPException(404, "not_found")
    return {
        "document_id": str(doc.id),
        "supersedes": str(doc.supersedes) if doc.supersedes else None,
        "is_addendum": bool(doc.meta.get("addendum")),
        "addendum_reason": doc.meta.get("addendum_reason"),
        "addendum_changes": doc.meta.get("addendum_changes", []),
        "duplicate_of": doc.meta.get("duplicate_of"),
        "ocr_status": doc.ocr_status,
    }


def _to_uuid(value: str):
    import uuid

    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None
