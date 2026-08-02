from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.claims.service import ClaimsError, ClaimsService

router = APIRouter()

_ERROR_STATUS = {
    "bad_claim_type": 400,
    "bad_request": 400,
    "bad_draft_kind": 400,
    "bad_response_kind": 400,
    "bad_negotiation_status": 400,
    "bad_outcome": 400,
    "bad_quantity": 400,
    "bad_rate": 400,
    "bad_delay_days": 400,
    "not_found": 404,
    "not_editable": 409,
    "bad_status_transition": 409,
    "chain_broken": 409,
    "approval_denied": 403,
    "event_opportunity_mismatch": 400,
    "claim_opportunity_mismatch": 400,
    "settlement_exists": 409,
}


class CreateClaimBody(BaseModel):
    claim_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    change_event_id: str | None = None
    baseline_id: str | None = None
    claim_amount_minor: int | None = None
    currency: str = "INR"


class UpdateClaimBody(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    claim_type: str | None = None
    claim_amount_minor: int | None = None
    currency: str | None = None


class LineItemBody(BaseModel):
    description: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1)
    rate_minor: int = Field(ge=0)
    daywork_days: int | None = Field(default=None, ge=0)
    daywork_rate_minor: int | None = Field(default=None, ge=0)
    cost_code_id: str | None = None
    currency: str | None = None


class UpdateLineItemBody(BaseModel):
    description: str | None = Field(default=None, min_length=1)
    quantity: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1)
    rate_minor: int | None = Field(default=None, ge=0)
    daywork_days: int | None = Field(default=None, ge=0)
    daywork_rate_minor: int | None = Field(default=None, ge=0)


class DelayEventBody(BaseModel):
    event_date: date
    description: str = Field(min_length=1)
    delay_days: int = Field(ge=0)
    programme_activity: str | None = None
    source_page: int | None = None
    source_quote: str | None = Field(default=None, max_length=200)
    document_id: str | None = None
    claim_id: str | None = None
    change_event_id: str | None = None


class ResponseBody(BaseModel):
    response_kind: str = Field(min_length=1)
    received_at: date
    responder: str = Field(min_length=1)
    due_at: date | None = None
    notes: str | None = None
    document_id: str | None = None


class NegotiationBody(BaseModel):
    offered_amount_minor: int = Field(ge=0)
    counter_amount_minor: int | None = Field(default=None, ge=0)
    status: str = "open"


class SettlementBody(BaseModel):
    outcome: str = Field(min_length=1)
    settled_amount_minor: int = Field(ge=0)
    notes: str | None = None


class OverrideBody(BaseModel):
    override_note: str = Field(min_length=1, max_length=500)


def _service(request: Request, session: Session) -> ClaimsService:
    reg = request.app.state.ctx.registry
    factory = reg.get("claims.service_factory")
    if factory:
        return factory(session)
    return ClaimsService(
        session,
        change_factory=reg.get("change.service_factory"),
        evidence_factory=reg.get("evidence.service_factory"),
        baseline_factory=reg.get("baseline.service_factory"),
        approval_matrix_factory=reg.get("auth.approval_matrix"),
        ingestion_factory=reg.get("ingestion.service_factory"),
        drafting_factory=reg.get("drafting.service_factory"),
        outcomes_factory=reg.get("outcomes.service_factory"),
        analytics_factory=reg.get("analytics.service_factory"),
        publish=request.app.state.ctx.events.publish,
    )


def _raise(exc: ClaimsError) -> None:
    status = _ERROR_STATUS.get(exc.code, 400)
    raise HTTPException(status, {"code": exc.code, **exc.detail}) from exc


@router.get("/opportunities/{opportunity_id}/claims")
def list_claims(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        claims = _service(request, session).list_claims(
            principal.workspace_id, opportunity_id
        )
        return {"claims": claims}
    except ClaimsError as exc:
        _raise(exc)


@router.post("/opportunities/{opportunity_id}/claims")
def create_claim(
    opportunity_id: str,
    body: CreateClaimBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).create_claim(
            principal.workspace_id,
            opportunity_id,
            claim_type=body.claim_type,
            title=body.title,
            description=body.description,
            change_event_id=body.change_event_id,
            baseline_id=body.baseline_id,
            claim_amount_minor=body.claim_amount_minor,
            currency=body.currency,
            created_by=principal.user_id,
        )
    except ClaimsError as exc:
        _raise(exc)


@router.get("/claims/{claim_id}")
def get_claim(
    claim_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).get_claim(principal.workspace_id, claim_id)
    except ClaimsError as exc:
        _raise(exc)


@router.put("/claims/{claim_id}")
def update_claim(
    claim_id: str,
    body: UpdateClaimBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).update_claim(
            principal.workspace_id,
            claim_id,
            title=body.title,
            description=body.description,
            claim_type=body.claim_type,
            claim_amount_minor=body.claim_amount_minor,
            currency=body.currency,
        )
    except ClaimsError as exc:
        _raise(exc)


@router.post("/claims/{claim_id}/submit")
def submit_claim(
    claim_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).submit_claim(
            principal.workspace_id, claim_id, principal.user_id
        )
    except ClaimsError as exc:
        _raise(exc)


@router.get("/claims/{claim_id}/chronology")
def chronology(
    claim_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        entries = _service(request, session).chronology_for_claim(
            principal.workspace_id, claim_id
        )
        return {"entries": entries}
    except ClaimsError as exc:
        _raise(exc)


@router.get("/claims/{claim_id}/checklist")
def checklist(
    claim_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        items = _service(request, session).checklist_for_claim(
            principal.workspace_id, claim_id
        )
        return {"items": items}
    except ClaimsError as exc:
        _raise(exc)


@router.post("/claims/{claim_id}/checklist/{item_id}/override")
def override_checklist_item(
    claim_id: str,
    item_id: str,
    body: OverrideBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).override_checklist_item(
            principal.workspace_id,
            claim_id,
            item_id,
            override_note=body.override_note,
        )
    except ClaimsError as exc:
        _raise(exc)


@router.get("/claims/{claim_id}/quantum")
def quantum(
    claim_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).quantum_for_claim(principal.workspace_id, claim_id)
    except ClaimsError as exc:
        _raise(exc)


@router.post("/claims/{claim_id}/quantum/line-items")
def add_line_item(
    claim_id: str,
    body: LineItemBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).add_line_item(
            principal.workspace_id,
            claim_id,
            description=body.description,
            quantity=body.quantity,
            unit=body.unit,
            rate_minor=body.rate_minor,
            daywork_days=body.daywork_days,
            daywork_rate_minor=body.daywork_rate_minor,
            cost_code_id=body.cost_code_id,
            currency=body.currency,
            created_by=principal.user_id,
        )
    except ClaimsError as exc:
        _raise(exc)


@router.put("/claims/{claim_id}/quantum/line-items/{line_id}")
def update_line_item(
    claim_id: str,
    line_id: str,
    body: UpdateLineItemBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).update_line_item(
            principal.workspace_id,
            claim_id,
            line_id,
            description=body.description,
            quantity=body.quantity,
            unit=body.unit,
            rate_minor=body.rate_minor,
            daywork_days=body.daywork_days,
            daywork_rate_minor=body.daywork_rate_minor,
        )
    except ClaimsError as exc:
        _raise(exc)


@router.delete("/claims/{claim_id}/quantum/line-items/{line_id}")
def delete_line_item(
    claim_id: str,
    line_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        _service(request, session).delete_line_item(principal.workspace_id, claim_id, line_id)
        return {"ok": True}
    except ClaimsError as exc:
        _raise(exc)


@router.get("/opportunities/{opportunity_id}/delay-register")
def list_delay_events(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        events = _service(request, session).list_delay_events(
            principal.workspace_id, opportunity_id
        )
        return {"events": events}
    except ClaimsError as exc:
        _raise(exc)


@router.post("/opportunities/{opportunity_id}/delay-register")
def add_delay_event(
    opportunity_id: str,
    body: DelayEventBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).add_delay_event(
            principal.workspace_id,
            opportunity_id,
            event_date=body.event_date,
            description=body.description,
            delay_days=body.delay_days,
            programme_activity=body.programme_activity,
            source_page=body.source_page,
            source_quote=body.source_quote,
            document_id=body.document_id,
            claim_id=body.claim_id,
            change_event_id=body.change_event_id,
            created_by=principal.user_id,
        )
    except ClaimsError as exc:
        _raise(exc)


@router.post("/claims/{claim_id}/responses")
def record_response(
    claim_id: str,
    body: ResponseBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).record_response(
            principal.workspace_id,
            claim_id,
            response_kind=body.response_kind,
            received_at=body.received_at,
            responder=body.responder,
            due_at=body.due_at,
            notes=body.notes,
            document_id=body.document_id,
            created_by=principal.user_id,
        )
    except ClaimsError as exc:
        _raise(exc)


@router.post("/claims/{claim_id}/negotiations")
def record_negotiation(
    claim_id: str,
    body: NegotiationBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).record_negotiation(
            principal.workspace_id,
            claim_id,
            offered_amount_minor=body.offered_amount_minor,
            counter_amount_minor=body.counter_amount_minor,
            status=body.status,
            recorded_by=principal.user_id,
        )
    except ClaimsError as exc:
        _raise(exc)


@router.post("/claims/{claim_id}/settlement")
def record_settlement(
    claim_id: str,
    body: SettlementBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).record_settlement(
            principal.workspace_id,
            claim_id,
            outcome=body.outcome,
            settled_amount_minor=body.settled_amount_minor,
            notes=body.notes,
            recorded_by=principal.user_id,
        )
    except ClaimsError as exc:
        _raise(exc)


@router.get("/claims/{claim_id}/timeline")
def timeline(
    claim_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).negotiation_timeline(principal.workspace_id, claim_id)
    except ClaimsError as exc:
        _raise(exc)


@router.post("/claims/{claim_id}/drafts/{kind}")
def generate_draft(
    claim_id: str,
    kind: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).generate_draft(
            principal.workspace_id, claim_id, kind, created_by=principal.user_id
        )
    except ClaimsError as exc:
        _raise(exc)


@router.get("/claims/{claim_id}/drafts")
def list_drafts(
    claim_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return {"drafts": _service(request, session).list_drafts(principal.workspace_id, claim_id)}
    except ClaimsError as exc:
        _raise(exc)


@router.get("/drafts/{draft_id}")
def get_draft(
    draft_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).get_draft(principal.workspace_id, draft_id)
    except ClaimsError as exc:
        _raise(exc)


@router.post("/drafts/{draft_id}/approve")
def approve_draft(
    draft_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("reviewer")),
):
    try:
        return _service(request, session).approve_draft(
            principal.workspace_id, draft_id, approved_by=principal.user_id
        )
    except ClaimsError as exc:
        _raise(exc)


@router.get("/claims/{claim_id}/chain-integrity")
def chain_integrity(
    claim_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).chain_integrity(principal.workspace_id, claim_id)
    except ClaimsError as exc:
        _raise(exc)


@router.get("/claims/{claim_id}/conflicts")
def conflicts(
    claim_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return _service(request, session).conflict_check(principal.workspace_id, claim_id)
    except ClaimsError as exc:
        _raise(exc)


@router.get("/opportunities/{opportunity_id}/claim-metrics")
def claim_metrics(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).cycle_metrics(principal.workspace_id, opportunity_id)
    except ClaimsError as exc:
        _raise(exc)
