"""Subcontract control API (TS-288, TS-289)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.subcontract.service import SubcontractError, SubcontractService

router = APIRouter()

_ERROR_STATUS = {
    "not_found": 404,
    "baseline_unavailable": 503,
    "change_unavailable": 503,
}


class CreateSubcontractBody(BaseModel):
    subcontractor_name: str = Field(min_length=1)
    reference: str | None = None
    contract_value_minor: int | None = None
    currency: str = "INR"
    scope: str | None = None
    notice_buffer_days: int = 7
    postal_buffer_days: int = 2


class CreateClauseBody(BaseModel):
    title: str = Field(min_length=1)
    source_quote: str | None = None
    present: bool | None = None
    status: str = "unchecked"


class CreateScopeItemBody(BaseModel):
    item_text: str = Field(min_length=1)
    covered: bool = False
    source_event_id: str | None = None


class CreatePaymentEventBody(BaseModel):
    kind: str = Field(min_length=1)
    due_date: date
    amount_minor: int = Field(ge=0)
    certified_amount_minor: int | None = Field(default=None, ge=0)
    currency: str = "INR"
    status: str = "pending"
    parent_payment_status: str | None = None


def _service(request: Request, session: Session) -> SubcontractService:
    reg = request.app.state.ctx.registry
    return SubcontractService(
        session,
        baseline_factory=reg.get("baseline.service_factory"),
        change_factory=reg.get("change.service_factory"),
        publish=request.app.state.ctx.events.publish,
    )


def _raise(exc: SubcontractError):
    raise HTTPException(_ERROR_STATUS.get(exc.code, 400), exc.code) from exc


@router.get("/status")
def status() -> dict:
    return {"module": "subcontract", "status": "ready"}


@router.post("/opportunities/{opportunity_id}/subcontracts")
def create_subcontract(
    opportunity_id: str,
    body: CreateSubcontractBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        row = _service(request, session).create_subcontract(
            principal.workspace_id,
            opportunity_id,
            subcontractor_name=body.subcontractor_name,
            created_by=principal.user_id,
            reference=body.reference,
            contract_value_minor=body.contract_value_minor,
            currency=body.currency,
            scope=body.scope,
            notice_buffer_days=body.notice_buffer_days,
            postal_buffer_days=body.postal_buffer_days,
        )
    except SubcontractError as exc:
        _raise(exc)
    return {"id": str(row.id), "subcontractor_name": row.subcontractor_name}


@router.get("/opportunities/{opportunity_id}/subcontracts")
def list_subcontracts(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    rows = _service(request, session).list_subcontracts(principal.workspace_id, opportunity_id)
    return {"subcontracts": [_service(request, session)._subcontract_dict(r) for r in rows]}


@router.get("/subcontracts/{subcontract_id}")
def get_subcontract(
    subcontract_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        row = _service(request, session).get_subcontract(principal.workspace_id, subcontract_id)
    except SubcontractError as exc:
        _raise(exc)
    return _service(request, session)._subcontract_dict(row)


@router.post("/subcontracts/{subcontract_id}/clauses")
def add_clause(
    subcontract_id: str,
    body: CreateClauseBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        row = _service(request, session).add_clause(
            principal.workspace_id,
            subcontract_id,
            title=body.title,
            source_quote=body.source_quote,
            present=body.present,
            status=body.status,
        )
    except SubcontractError as exc:
        _raise(exc)
    return {"id": str(row.id), "title": row.title}


@router.get("/subcontracts/{subcontract_id}/flowdown-check")
def flowdown_check(
    subcontract_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).flowdown_check(principal.workspace_id, subcontract_id)
    except SubcontractError as exc:
        _raise(exc)


@router.post("/subcontracts/{subcontract_id}/scope-items")
def add_scope_item(
    subcontract_id: str,
    body: CreateScopeItemBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        row = _service(request, session).add_scope_item(
            principal.workspace_id,
            subcontract_id,
            item_text=body.item_text,
            covered=body.covered,
            source_event_id=body.source_event_id,
        )
    except SubcontractError as exc:
        _raise(exc)
    return {"id": str(row.id), "item_text": row.item_text}


@router.get("/subcontracts/{subcontract_id}/scope-gaps")
def scope_gaps(
    subcontract_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).scope_gaps(principal.workspace_id, subcontract_id)
    except SubcontractError as exc:
        _raise(exc)


@router.get("/subcontracts/{subcontract_id}/notice-calendar")
def notice_calendar(
    subcontract_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).notice_calendar(
            principal.workspace_id, subcontract_id
        )
    except SubcontractError as exc:
        _raise(exc)


@router.post("/subcontracts/{subcontract_id}/payment-events")
def add_payment_event(
    subcontract_id: str,
    body: CreatePaymentEventBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        row = _service(request, session).add_payment_event(
            principal.workspace_id,
            subcontract_id,
            kind=body.kind,
            due_date=body.due_date,
            amount_minor=body.amount_minor,
            certified_amount_minor=body.certified_amount_minor,
            currency=body.currency,
            status=body.status,
            parent_payment_status=body.parent_payment_status,
        )
    except SubcontractError as exc:
        _raise(exc)
    return {"id": str(row.id), "kind": row.kind, "amount_minor": row.amount_minor}


@router.get("/subcontracts/{subcontract_id}/payment-exposure")
def payment_exposure(
    subcontract_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).payment_exposure(
            principal.workspace_id, subcontract_id
        )
    except SubcontractError as exc:
        _raise(exc)
