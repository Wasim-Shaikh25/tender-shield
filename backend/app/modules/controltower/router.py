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


def _service(request: Request, session: Session) -> ControlTowerService:
    reg = request.app.state.ctx.registry
    return ControlTowerService(
        session,
        ingestion_factory=reg.get("ingestion.service_factory"),
        claims_factory=reg.get("claims.service_factory"),
        change_factory=reg.get("change.service_factory"),
        evidence_factory=reg.get("evidence.service_factory"),
        outcomes_factory=reg.get("outcomes.service_factory"),
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
