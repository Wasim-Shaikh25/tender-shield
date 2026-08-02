from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.controltower.service import ControlTowerError, ControlTowerService

router = APIRouter()


class CostOfCapitalParams(BaseModel):
    cost_of_capital_pa: float = Field(default=0.12, ge=0.0)
    currency: str = "INR"


class ForecastBody(BaseModel):
    opportunity_id: str
    projected_final_cost_minor: int = Field(ge=0)
    contingency_percent: float = Field(default=0.0, ge=0.0)
    cost_of_capital_pa: float = Field(default=0.12, ge=0.0)
    currency: str = "INR"


class PaymentEventBody(BaseModel):
    opportunity_id: str
    kind: str = Field(pattern="^(ra|progress|retention|security)$")
    due_date: date
    amount_minor: int = Field(ge=0)
    certified_amount_minor: int | None = Field(default=None, ge=0)
    currency: str = "INR"
    status: str = Field(default="pending", pattern="^(pending|certified|released)$")
    released_at: datetime | None = None
    description: str | None = None


class EconomicsParams(BaseModel):
    cost_of_sales_minor: int | None = Field(default=None, ge=0)
    customer_acquisition_cost_minor: int | None = Field(default=None, ge=0)
    currency: str = "INR"


class OutcomeParams(BaseModel):
    hours_per_review_saved: float = Field(default=2.0, ge=0.0)
    currency: str = "INR"


def _service(request: Request, session: Session) -> ControlTowerService:
    reg = request.app.state.ctx.registry
    return ControlTowerService(
        session,
        ingestion_factory=reg.get("ingestion.service_factory"),
        claims_factory=reg.get("claims.service_factory"),
        change_factory=reg.get("change.service_factory"),
        evidence_factory=reg.get("evidence.service_factory"),
        findings_factory=reg.get("findings.store_factory"),
        outcomes_factory=reg.get("outcomes.service_factory"),
        billing_factory=reg.get("billing.service_factory"),
        publish=request.app.state.ctx.events.publish,
    )


@router.get("/exposure")
def get_exposure(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    params: CostOfCapitalParams = Depends(),
):
    try:
        return _service(request, session).exposure_for_opportunity(
            principal.workspace_id,
            opportunity_id,
            cost_of_capital_pa=params.cost_of_capital_pa,
            currency=params.currency,
        )
    except ControlTowerError as exc:
        status = 503 if exc.code == "ingestion_unavailable" else 404
        raise HTTPException(status, exc.code) from exc


@router.get("/dashboard")
def get_dashboard(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    currency: str = "INR",
):
    try:
        return _service(request, session).dashboard_for_opportunity(
            principal.workspace_id,
            opportunity_id,
            currency=currency,
        )
    except ControlTowerError as exc:
        status = 503 if exc.code == "ingestion_unavailable" else 404
        raise HTTPException(status, exc.code) from exc


@router.get("/portfolio")
def get_portfolio(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    params: CostOfCapitalParams = Depends(),
):
    return _service(request, session).portfolio_summary(
        principal.workspace_id,
        cost_of_capital_pa=params.cost_of_capital_pa,
        currency=params.currency,
    )


@router.post("/forecast")
def post_forecast(
    body: ForecastBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).forecast_for_opportunity(
            principal.workspace_id,
            body.opportunity_id,
            projected_final_cost_minor=body.projected_final_cost_minor,
            contingency_percent=body.contingency_percent,
            cost_of_capital_pa=body.cost_of_capital_pa,
            currency=body.currency,
        )
    except ControlTowerError as exc:
        status = 503 if exc.code == "ingestion_unavailable" else 404
        raise HTTPException(status, exc.code) from exc


@router.get("/response-times")
def get_response_times(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).response_times_for_opportunity(
        principal.workspace_id, opportunity_id
    )


@router.get("/clause-trends")
def get_clause_trends(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).clause_trends_for_workspace(principal.workspace_id)


@router.get("/recurring-omissions")
def get_recurring_omissions(
    request: Request,
    opportunity_id: str | None = None,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).recurring_omissions_for_workspace(
        principal.workspace_id, current_opportunity_id=opportunity_id
    )


@router.get("/executive-summary")
def get_executive_summary(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    params: CostOfCapitalParams = Depends(),
):
    try:
        return _service(request, session).executive_summary_for_opportunity(
            principal.workspace_id,
            opportunity_id,
            cost_of_capital_pa=params.cost_of_capital_pa,
            currency=params.currency,
        )
    except ControlTowerError as exc:
        status = 503 if exc.code == "ingestion_unavailable" else 404
        raise HTTPException(status, exc.code) from exc


@router.get("/payment-schedule")
def get_payment_schedule(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).payment_schedule_for_opportunity(
        principal.workspace_id, opportunity_id
    )


@router.post("/payment-schedule")
def post_payment_event(
    body: PaymentEventBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        return _service(request, session).record_payment_event(
            principal.workspace_id,
            body.opportunity_id,
            kind=body.kind,
            due_date=body.due_date,
            amount_minor=body.amount_minor,
            certified_amount_minor=body.certified_amount_minor,
            currency=body.currency,
            status=body.status,
            released_at=body.released_at,
            description=body.description,
            created_by=principal.user_id,
        )
    except ControlTowerError as exc:
        raise HTTPException(400, exc.code) from exc


@router.get("/economics")
def get_economics(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    params: EconomicsParams = Depends(),
):
    return _service(request, session).economics_for_workspace(
        principal.workspace_id,
        cost_of_sales_minor=params.cost_of_sales_minor,
        customer_acquisition_cost_minor=params.customer_acquisition_cost_minor,
        currency=params.currency,
    )


@router.get("/customer-outcomes")
def get_customer_outcomes(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    params: OutcomeParams = Depends(),
):
    return _service(request, session).customer_outcomes_for_workspace(
        principal.workspace_id,
        hours_per_review_saved=params.hours_per_review_saved,
        currency=params.currency,
    )
