from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.evidence.service import EvidenceError, EvidenceService

router = APIRouter()

_ERROR_STATUS = {
    "not_found": 404,
    "bad_request": 400,
    "bad_record_type": 400,
    "change_unavailable": 503,
}


class AttachBody(BaseModel):
    record_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    captured_at: datetime | None = None
    document_id: str | None = None


def _service(request: Request, session: Session) -> EvidenceService:
    reg = request.app.state.ctx.registry
    factory = reg.get("evidence.service_factory")
    if factory:
        return factory(session)
    return EvidenceService(
        session,
        change_event_fn=reg.get("change.event_for_id"),
        publish=request.app.state.ctx.events.publish,
    )


def _raise(exc: EvidenceError) -> None:
    raise HTTPException(_ERROR_STATUS.get(exc.code, 400), exc.code) from exc


@router.post("/events/{event_id}/records")
def attach_record(
    event_id: str,
    body: AttachBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).attach(
            principal.workspace_id,
            event_id,
            record_type=body.record_type,
            title=body.title,
            description=body.description,
            captured_at=body.captured_at,
            document_id=body.document_id,
            created_by=principal.user_id,
        )
    except EvidenceError as exc:
        _raise(exc)


@router.get("/events/{event_id}/records")
def list_records(
    event_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return {
            "records": _service(request, session).list_for_event(
                principal.workspace_id, event_id
            )
        }
    except EvidenceError as exc:
        _raise(exc)


@router.get("/events/{event_id}/completeness")
def event_completeness(
    event_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).completeness_for_event(
            principal.workspace_id, event_id
        )
    except EvidenceError as exc:
        _raise(exc)


@router.get("/records/{record_id}")
def get_record(
    record_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).get(principal.workspace_id, record_id)
    except EvidenceError as exc:
        _raise(exc)
