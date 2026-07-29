from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.core.storage import StorageError, ValidationError, validate_and_store
from app.modules.baseline.service import BaselineError, BaselineService

router = APIRouter()

_ERROR_STATUS = {
    "review_incomplete": 403,
    "review_unavailable": 503,
    "findings_unavailable": 503,
    "ingestion_unavailable": 503,
    "not_found": 404,
    "opportunity_not_found": 404,
    "no_baseline": 404,
    "need_two_baselines": 409,
    "bad_source": 400,
}


def _service(request: Request, session: Session) -> BaselineService:
    reg = request.app.state.ctx.registry
    return BaselineService(
        session,
        findings_factory=reg.get("findings.store_factory"),
        review_factory=reg.get("review.service_factory"),
        ingestion_factory=reg.get("ingestion.service_factory"),
        loader_provider=lambda: reg.get("rulepacks.loader"),
        standards_factory=reg.get("standards.org_notice_provider"),
        publish=request.app.state.ctx.events.publish,
    )


def _raise(exc: BaselineError):
    raise HTTPException(_ERROR_STATUS.get(exc.code, 400), exc.code) from exc


def _baseline_dict(row) -> dict:
    return {
        "id": str(row.id),
        "version": row.version,
        "source": row.source,
        "content_sha256": row.content_sha256,
        "note": row.note,
        "sealed_at": row.sealed_at.isoformat() if row.sealed_at else None,
        "counts": row.snapshot.get("counts", {}),
    }


class FreezeBody(BaseModel):
    source: str = "tender"  # tender | award
    note: str | None = None


@router.post("/opportunities/{opportunity_id}/freeze")
def freeze(
    opportunity_id: str,
    body: FreezeBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("reviewer")),
):
    try:
        row = _service(request, session).freeze(
            principal.workspace_id,
            opportunity_id,
            source=body.source,
            note=body.note,
            sealer_id=principal.user_id,
        )
    except BaselineError as exc:
        _raise(exc)
    return _baseline_dict(row)


@router.post("/opportunities/{opportunity_id}/award-document")
async def upload_award_document(
    opportunity_id: str,
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    principal: Any = Depends(require("reviewer")),
):
    """Upload a negotiated contract / award letter so the award baseline seals from
    real award text."""
    data = await file.read()
    try:
        stored = await validate_and_store(
            request.app.state.ctx.settings,
            file.filename,
            file.content_type,
            data,
            workspace_id=str(principal.workspace_id),
        )
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(500, str(exc)) from exc
    try:
        doc = _service(request, session).store_award_document(
            principal.workspace_id,
            opportunity_id,
            file.filename,
            data,
            uploaded_by=principal.user_id,
        )
    except BaselineError as exc:
        _raise(exc)
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "chars": len(doc.text),
        "sha256": doc.sha256,
        "s3_key": stored.get("key"),
    }


@router.get("/opportunities/{opportunity_id}/baselines")
def list_baselines(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    rows = _service(request, session).list(principal.workspace_id, opportunity_id)
    return {"baselines": [_baseline_dict(r) for r in rows]}


@router.get("/baselines/{baseline_id}")
def get_baseline(
    baseline_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    row = _service(request, session).get(principal.workspace_id, baseline_id)
    if row is None:
        raise HTTPException(404, "not_found")
    return {**_baseline_dict(row), "snapshot": row.snapshot}


@router.get("/baselines/{baseline_id}/verify")
def verify_baseline(
    baseline_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).verify(principal.workspace_id, baseline_id)
    except BaselineError as exc:
        _raise(exc)


@router.get("/opportunities/{opportunity_id}/notice-register")
def notice_register(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).notice_register(principal.workspace_id, opportunity_id)
    except BaselineError as exc:
        _raise(exc)


@router.get("/opportunities/{opportunity_id}/compare")
def compare(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).compare(principal.workspace_id, opportunity_id)
    except BaselineError as exc:
        _raise(exc)


@router.get("/opportunities/{opportunity_id}/handover")
def handover(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).handover(principal.workspace_id, opportunity_id)
    except BaselineError as exc:
        _raise(exc)
