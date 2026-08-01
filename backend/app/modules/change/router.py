from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.change.service import ChangeError, ChangeService

router = APIRouter()

_ERROR_STATUS = {
    "baseline_unavailable": 503,
    "ingestion_unavailable": 503,
    "diff_unavailable": 503,
    "no_baseline": 404,
    "not_found": 404,
    "bad_request": 400,
    "source_required": 400,
    "quote_too_long": 400,
    "bad_outcome": 400,
    "bad_signal_kind": 400,
}


class SourceBody(BaseModel):
    source_kind: str = "manual"
    document_id: str | None = None
    source_page: int | None = None
    source_quote: str | None = Field(default=None, max_length=200)
    external_ref: str | None = None
    text_preview: str | None = None


class CreateEventBody(BaseModel):
    title: str = Field(min_length=1)
    reason: str = "other"
    affected_scope: str | None = None
    confidence_band: str = "medium"
    notice_type: str | None = None
    trigger_date: date | None = None
    sources: list[SourceBody] = Field(min_length=1)


class ConfirmationBody(BaseModel):
    outcome: str
    note: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class DiffBody(BaseModel):
    document_id: str | None = None
    text: str | None = Field(default=None, max_length=1_000_000)


class SignalBody(BaseModel):
    signal_kind: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=1_000_000)
    title: str | None = None
    external_ref: str | None = None


def _service(request: Request, session: Session) -> ChangeService:
    reg = request.app.state.ctx.registry
    factory = reg.get("change.service_factory")
    if factory:
        return factory(session)
    return ChangeService(
        session,
        baseline_factory=reg.get("baseline.service_factory"),
        ingestion_factory=reg.get("ingestion.service_factory"),
        review_factory=reg.get("review.service_factory"),
        segment_clauses_fn=reg.get("ingestion.segment_clauses"),
        diff_clauses_fn=reg.get("baseline.diff_clauses"),
        publish=request.app.state.ctx.events.publish,
    )


def _raise(exc: ChangeError) -> None:
    raise HTTPException(_ERROR_STATUS.get(exc.code, 400), exc.code) from exc


@router.get("/opportunities/{opportunity_id}/events")
def list_events(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return {
        "events": _service(request, session).list_events(
            principal.workspace_id, opportunity_id
        )
    }


@router.post("/opportunities/{opportunity_id}/events")
def create_event(
    opportunity_id: str,
    body: CreateEventBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).create_manual_event(
            principal.workspace_id,
            opportunity_id,
            title=body.title,
            reason=body.reason,
            affected_scope=body.affected_scope,
            confidence_band=body.confidence_band,
            notice_type=body.notice_type,
            trigger_date=body.trigger_date,
            created_by=principal.user_id,
            sources=[s.model_dump() for s in body.sources],
        )
    except ChangeError as exc:
        _raise(exc)


@router.get("/events/{event_id}")
def get_event(
    event_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).get_event(principal.workspace_id, event_id)
    except ChangeError as exc:
        _raise(exc)


@router.post("/events/{event_id}/confirmations")
def record_confirmation(
    event_id: str,
    body: ConfirmationBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).record_confirmation(
            principal.workspace_id,
            event_id,
            outcome=body.outcome,
            confirmed_by=principal.user_id,
            note=body.note,
            evidence_ids=body.evidence_ids,
        )
    except ChangeError as exc:
        _raise(exc)


@router.post("/opportunities/{opportunity_id}/diff")
def run_baseline_diff(
    opportunity_id: str,
    body: DiffBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    if not body.document_id and not body.text:
        raise HTTPException(400, "bad_request")
    try:
        return _service(request, session).run_baseline_diff(
            principal.workspace_id,
            opportunity_id,
            document_id=body.document_id,
            text=body.text,
            created_by=principal.user_id,
        )
    except ChangeError as exc:
        _raise(exc)


@router.post("/opportunities/{opportunity_id}/signals")
def ingest_signal(
    opportunity_id: str,
    body: SignalBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).ingest_signal(
            principal.workspace_id,
            opportunity_id,
            signal_kind=body.signal_kind,
            text=body.text,
            title=body.title,
            external_ref=body.external_ref,
            created_by=principal.user_id,
        )
    except ChangeError as exc:
        _raise(exc)
