"""Drawing register and comparison API (TS-321, TS-322)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.drawings.service import DrawingsError, DrawingService

router = APIRouter()


def _service(request: Request, session: Session) -> DrawingService:
    reg = request.app.state.ctx.registry
    return DrawingService(
        session,
        ocr_provider=reg.get("ingestion.ocr"),
    )


def _row_dict(row) -> dict:
    return {
        "id": str(row.id),
        "opportunity_id": str(row.opportunity_id),
        "document_id": str(row.document_id) if row.document_id else None,
        "filename": row.filename,
        "drawing_number": row.drawing_number,
        "title": row.title,
        "revision": row.revision,
        "revision_date": row.revision_date,
        "discipline": row.discipline,
        "supersedes_id": str(row.supersedes_id) if row.supersedes_id else None,
        "page_count": row.page_count,
        "title_block": row.title_block,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/opportunities/{opportunity_id}/drawings")
def list_drawings(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    rows = _service(request, session).list(principal.workspace_id, opportunity_id)
    return {"drawings": [_row_dict(r) for r in rows]}


@router.get("/opportunities/{opportunity_id}/drawings/{drawing_id}")
def get_drawing(
    opportunity_id: str,
    drawing_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    row = _service(request, session).get(principal.workspace_id, drawing_id)
    if not row:
        raise HTTPException(404, "drawing_not_found")
    return _row_dict(row)


class CreateDrawingBody(BaseModel):
    filename: str
    document_id: str | None = None
    drawing_number: str | None = None
    title: str | None = None
    revision: str | None = None
    revision_date: str | None = None
    discipline: str | None = None
    supersedes_id: str | None = None


@router.post("/opportunities/{opportunity_id}/drawings")
def create_drawing(
    opportunity_id: str,
    body: CreateDrawingBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    row = _service(request, session).create(
        principal.workspace_id,
        opportunity_id,
        filename=body.filename,
        document_id=body.document_id,
        drawing_number=body.drawing_number,
        title=body.title,
        revision=body.revision,
        revision_date=body.revision_date,
        discipline=body.discipline,
        supersedes_id=body.supersedes_id,
    )
    return _row_dict(row)


@router.post("/opportunities/{opportunity_id}/drawings/{drawing_id}/upload")
async def upload_drawing(
    opportunity_id: str,
    drawing_id: str,
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    svc = _service(request, session)
    existing = svc.get(principal.workspace_id, drawing_id)
    if not existing:
        raise HTTPException(404, "drawing_not_found")
    data = await file.read(50_000_000)
    if len(data) > 50_000_000:
        raise HTTPException(413, "upload_too_large")
    updated = svc.update_extraction(
        principal.workspace_id,
        drawing_id,
        file_data=data,
        filename=file.filename or existing.filename,
    )
    return _row_dict(updated)


@router.post("/opportunities/{opportunity_id}/drawings/{current_id}/supersedes/{previous_id}")
def supersede_drawing(
    opportunity_id: str,
    current_id: str,
    previous_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        row = _service(request, session).supersede(principal.workspace_id, current_id, previous_id)
    except DrawingsError as exc:
        raise HTTPException(404, exc.code) from exc
    return _row_dict(row)


@router.post("/opportunities/{opportunity_id}/drawings/{current_id}/compare/{previous_id}")
def compare_drawings(
    opportunity_id: str,
    current_id: str,
    previous_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        comp = _service(request, session).compare(
            principal.workspace_id, current_id, previous_id
        )
    except DrawingsError as exc:
        raise HTTPException(404, exc.code) from exc
    return {
        "id": str(comp.id),
        "opportunity_id": str(comp.opportunity_id),
        "current_drawing_id": str(comp.current_drawing_id),
        "previous_drawing_id": str(comp.previous_drawing_id),
        "summary": comp.summary,
        "changed_pages": comp.changed_pages,
        "changed_regions": comp.changed_regions,
        "created_at": comp.created_at.isoformat() if comp.created_at else None,
    }
