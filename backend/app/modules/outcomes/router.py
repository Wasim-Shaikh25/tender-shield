"""Outcomes API (TS-215, spec §API routes)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.outcomes.service import OutcomesError, OutcomesService

router = APIRouter()

_ERROR_STATUS = {
    "bad_result": 422,
    "bad_amount": 400,
    "findings_unavailable": 503,
    "finding_not_found": 404,
}


class OutcomeBody(BaseModel):
    result: str
    quoted_value_minor: int | None = None
    l1_value_minor: int | None = None
    currency: str = "INR"
    bidder_count: int | None = None
    decline_reason: str | None = None


class MaterializedBody(BaseModel):
    opportunity_id: str
    materialized: bool = True
    impact_amount_minor: int | None = None
    currency: str = "INR"
    narrative: str | None = Field(default=None, max_length=2000)


def _service(request: Request, session: Session) -> OutcomesService:
    reg = request.app.state.ctx.registry
    return OutcomesService(
        session,
        findings_factory=reg.get("findings.store_factory"),
        comparable_awards=reg.get("marketdata.comparable_awards"),
        award_prefill=reg.get("marketdata.award_prefill"),
        publish=request.app.state.ctx.events.publish,
    )


def _raise(exc: OutcomesError):
    raise HTTPException(_ERROR_STATUS.get(exc.code, 400), exc.code) from exc


@router.get("")
def status() -> dict:
    return {"module": "outcomes", "status": "ready"}


@router.get("/metrics/margin-protected")
def margin_protected(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    currency: str = "INR",
):
    try:
        return _service(request, session).margin_protected(
            principal.workspace_id, currency=currency
        )
    except OutcomesError as exc:
        _raise(exc)


@router.post("/opportunities/{opportunity_id}")
def record_outcome(
    opportunity_id: str,
    body: OutcomeBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        row = _service(request, session).record_bid_outcome(
            principal.workspace_id,
            opportunity_id,
            result=body.result,
            quoted_value_minor=body.quoted_value_minor,
            l1_value_minor=body.l1_value_minor,
            currency=body.currency,
            bidder_count=body.bidder_count,
            decline_reason=body.decline_reason,
            recorded_by=principal.user_id,
        )
    except OutcomesError as exc:
        _raise(exc)
    return {
        "id": str(row.id),
        "opportunity_id": str(row.opportunity_id),
        "result": row.result,
    }


@router.get("/opportunities/{opportunity_id}")
def get_outcome(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    tender_ref: str | None = None,
):
    return _service(request, session).for_opportunity(
        principal.workspace_id, opportunity_id, tender_ref=tender_ref
    )


@router.post("/findings/{finding_id}/materialized")
def mark_materialized(
    finding_id: str,
    body: MaterializedBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        row = _service(request, session).mark_materialized(
            principal.workspace_id,
            finding_id,
            opportunity_id=body.opportunity_id,
            materialized=body.materialized,
            impact_amount_minor=body.impact_amount_minor,
            currency=body.currency,
            narrative=body.narrative,
            recorded_by=principal.user_id,
        )
    except OutcomesError as exc:
        _raise(exc)
    return {
        "id": str(row.id),
        "finding_id": str(row.finding_id),
        "materialized": row.materialized,
    }
