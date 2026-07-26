from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.ingestion.extract import extract_upload
from app.modules.ingestion.service import IngestionService
from app.modules.ingestion.storage import LocalStorage

MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB cap (Doc §11.2)

router = APIRouter()


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


class RegisterDocumentBody(BaseModel):
    filename: str = Field(min_length=1)
    sample_text: str = ""
    supersedes: str | None = None


@router.get("/opportunities")
def list_opportunities(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    opps = _service(request, session).list_opportunities(principal.org_id)
    return {"opportunities": [_opp_json(o) for o in opps]}


def _opp_json(o) -> dict:
    return {
        "id": str(o.id),
        "title": o.title,
        "status": o.status,
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
        principal.org_id,
        body.title,
        employer=body.employer,
        employer_family=body.employer_family,
        jurisdiction=body.jurisdiction,
    )
    return _opp_json(opp)


@router.get("/opportunities/{opportunity_id}")
def get_opportunity(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    opp = _service(request, session).get_opportunity(principal.org_id, opportunity_id)
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
    if not svc.get_opportunity(principal.org_id, opportunity_id):
        raise HTTPException(404, "not_found")
    doc = svc.register_document(
        principal.org_id, opportunity_id, body.filename, body.sample_text,
        uploaded_by=_to_uuid(principal.user_id),
        supersedes=_to_uuid(body.supersedes),
    )
    return {"id": str(doc.id), "filename": doc.filename, "kind": doc.kind}


@router.post("/opportunities/{opportunity_id}/upload")
async def upload_document(
    opportunity_id: str,
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    """Real multipart upload → store file → extract text (PDF/XLSX/CSV) → run the
    classify/segment/deadline pipeline."""
    svc = _service(request, session)
    if not svc.get_opportunity(principal.org_id, opportunity_id):
        raise HTTPException(404, "not_found")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "file_too_large")
    storage = LocalStorage(request.app.state.ctx.settings.storage_dir)
    key, sha = storage.put(str(principal.org_id), file.filename, data)
    ocr = request.app.state.ctx.registry.get("ingestion.ocr")
    text, ocr_status = extract_upload(file.filename, data, ocr)
    doc = svc.register_document(
        principal.org_id, opportunity_id, file.filename, text,
        s3_key=key, sha256=sha, ocr_status=ocr_status, uploaded_by=_to_uuid(principal.user_id),
    )
    return {
        "id": str(doc.id), "filename": doc.filename, "kind": doc.kind,
        "chars": len(text), "ocr_status": ocr_status,
    }


@router.get("/opportunities/{opportunity_id}/clauses")
def list_clauses(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    clauses = _service(request, session).list_clauses(principal.org_id, opportunity_id)
    return {
        "clauses": [
            {
                "id": str(c.id),
                "clause_ref": c.clause_ref,
                "heading": c.heading,
                "page_from": c.page_from,
                "cross_refs": c.cross_refs,
            }
            for c in clauses
        ]
    }


@router.get("/opportunities/{opportunity_id}/deadlines")
def list_deadlines(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    deadlines = _service(request, session).list_deadlines(principal.org_id, opportunity_id)
    return {
        "deadlines": [
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
    }


@router.post("/opportunities/{opportunity_id}/deadlines/{deadline_id}/confirm")
def confirm_deadline(
    opportunity_id: str,
    deadline_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    dl = _service(request, session).confirm_deadline(principal.org_id, deadline_id)
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
    return _service(request, session).missing_doc_report(principal.org_id, opportunity_id)


def _to_uuid(value: str):
    import uuid

    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None
