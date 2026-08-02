from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.core.ratelimit import RateLimitDep
from app.modules.change.email_inbox import verify_inbound_signature
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
    "bad_triage_decision": 400,
    "bad_triage_transition": 409,
    "bad_confirmation_state": 409,
    "invalid_cost_code": 400,
    "invalid_finding": 400,
    "notice_deadline_requires_confirmation": 409,
    "notice_draft_requires_confirmation": 409,
    "drafting_unavailable": 503,
    "no_verified_facts": 400,
    "approval_denied": 403,
    "role_below_minimum": 403,
    "document_class_forbidden": 403,
    "amount_above_limit": 403,
    "evidence_unavailable": 503,
    "billing_required": 402,
    "polling_disabled": 403,
    "no_trigger_date": 400,
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


class SignalMessage(BaseModel):
    signal_kind: str = "email"
    subject: str | None = None
    body: str = Field(min_length=1, max_length=1_000_000)
    external_ref: str | None = None


class SignalPollBody(BaseModel):
    messages: list[SignalMessage] = Field(default_factory=list)


class DelayAnalysisBody(BaseModel):
    event_id: str = Field(min_length=1)
    delay_days: int = Field(ge=1)


class TriageBody(BaseModel):
    decision: str = Field(min_length=1)


class ImpactLinksBody(BaseModel):
    boq_src_rows: list[str] = Field(default_factory=list)
    cost_code_ids: list[str] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    subcontract_refs: list[str] = Field(default_factory=list)


class EvidenceBody(BaseModel):
    record_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    captured_at: datetime | None = None
    document_id: str | None = None
    metadata: dict | None = None


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
        findings_factory=reg.get("findings.store_factory"),
        cost_codes_fn=reg.get("baseline.cost_codes_for_opportunity"),
        approval_matrix_factory=reg.get("auth.approval_matrix"),
        drafting_factory=reg.get("drafting.service_factory"),
        evidence_factory=reg.get("evidence.service_factory"),
        project_active_fn=reg.get("billing.is_project_active"),
        inbox_domain=request.app.state.ctx.settings.change_inbox_domain,
        publish=request.app.state.ctx.events.publish,
        poll_enabled=request.app.state.ctx.settings.change_signal_polling_enabled,
        schedule_activities_fn=reg.get("integrations.schedule_activities_for_opportunity"),
        document_class_permitted_fn=reg.get("auth.document_class_permitted"),
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
            actor_role=principal.role,
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


@router.post("/opportunities/{opportunity_id}/signals/poll")
def poll_signals(
    opportunity_id: str,
    body: SignalPollBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).poll_signals(
            principal.workspace_id,
            opportunity_id,
            messages=[m.model_dump() for m in body.messages],
            created_by=principal.user_id,
        )
    except ChangeError as exc:
        _raise(exc)


@router.post("/opportunities/{opportunity_id}/delay-analysis")
def delay_analysis(
    opportunity_id: str,
    body: DelayAnalysisBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).delay_analysis(
            principal.workspace_id,
            opportunity_id,
            event_id=body.event_id,
            delay_days=body.delay_days,
        )
    except ChangeError as exc:
        _raise(exc)


@router.get("/opportunities/{opportunity_id}/inbox")
def list_inbox(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).list_inbox(principal.workspace_id, opportunity_id)


@router.put("/events/{event_id}/triage")
def triage_event(
    event_id: str,
    body: TriageBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).triage_event(
            principal.workspace_id,
            event_id,
            decision=body.decision,
            actor_user_id=principal.user_id,
        )
    except ChangeError as exc:
        _raise(exc)


@router.put("/events/{event_id}/impacts")
def update_impacts(
    event_id: str,
    body: ImpactLinksBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).update_impacts(
            principal.workspace_id,
            event_id,
            impact_links=body.model_dump(),
        )
    except ChangeError as exc:
        _raise(exc)


@router.get("/events/{event_id}/confirmations")
def list_confirmations(
    event_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return {
            "confirmations": _service(request, session).list_confirmations(
                principal.workspace_id, event_id
            )
        }
    except ChangeError as exc:
        _raise(exc)


@router.get("/events/{event_id}/notice-deadline")
def get_notice_deadline(
    event_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).compute_notice_deadline(
            principal.workspace_id, event_id
        )
    except ChangeError as exc:
        _raise(exc)


@router.post("/events/{event_id}/notice-draft")
def request_notice_draft(
    event_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).request_notice_draft(
            principal.workspace_id,
            event_id,
            actor_user_id=principal.user_id,
            actor_role=getattr(principal, "role", "estimator"),
        )
    except ChangeError as exc:
        _raise(exc)


@router.post("/events/{event_id}/evidence")
def attach_evidence(
    event_id: str,
    body: EvidenceBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).attach_evidence(
            principal.workspace_id,
            event_id,
            record_type=body.record_type,
            title=body.title,
            description=body.description,
            captured_at=body.captured_at,
            document_id=body.document_id,
            metadata=body.metadata,
            created_by=principal.user_id,
        )
    except ChangeError as exc:
        _raise(exc)


@router.post("/opportunities/{opportunity_id}/inbox/email")
def register_inbox_email(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return _service(request, session).register_inbox_email(
            principal.workspace_id, opportunity_id
        )
    except ChangeError as exc:
        _raise(exc)


@router.get("/opportunities/{opportunity_id}/inbox/email")
def get_inbox_email(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return _service(request, session).get_inbox_email(
            principal.workspace_id, opportunity_id
        )
    except ChangeError as exc:
        _raise(exc)


class InboundEmailBody(BaseModel):
    address_token: str = Field(min_length=1)
    message_id: str = Field(min_length=1)
    from_address: str | None = Field(default=None, alias="from")
    subject: str | None = None
    body_plain: str = Field(min_length=1, max_length=500_000)
    received_at: str | None = None

    model_config = {"populate_by_name": True}


@router.post("/webhooks/inbound-email", dependencies=[Depends(RateLimitDep(50, 60))])
async def inbound_email_webhook(
    request: Request,
    session: Session = Depends(get_session),
):
    secret = request.app.state.ctx.settings.change_email_webhook_secret
    secret_val = secret.get_secret_value() if secret else None
    raw = await request.body()
    signature = request.headers.get("X-Change-Inbox-Signature", "")
    if not verify_inbound_signature(raw, signature, secret_val):
        raise HTTPException(400, "bad_signature")
    try:
        payload = InboundEmailBody.model_validate_json(raw)
    except Exception as exc:
        raise HTTPException(400, "bad_request") from exc
    try:
        return _service(request, session).process_inbound_email(
            payload.address_token,
            payload.model_dump(by_alias=True),
        )
    except ChangeError as exc:
        _raise(exc)
