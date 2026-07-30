from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.analytics.plan_agent import PlanDashboardAgent
from app.modules.analytics.service import AnalyticsService


class PlanQueryBody(BaseModel):
    opportunity_id: str = Field(min_length=1)
    query: str = Field(min_length=1)

router = APIRouter()


def _service(request: Request, session: Session) -> AnalyticsService:
    reg = request.app.state.ctx.registry
    factory = reg.get("analytics.service_factory")
    if factory:
        return factory(session)
    return AnalyticsService(
        session,
        findings_factory=reg.get("findings.store_factory"),
        ingestion_factory=reg.get("ingestion.service_factory"),
    )


@router.get("/accuracy")
def accuracy_dashboard(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    return _service(request, session).accuracy_dashboard(principal.workspace_id)


@router.get("/risk-summary")
def risk_summary(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).risk_summary(principal.workspace_id)


@router.get("/deadline-dashboard")
def deadline_dashboard(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).deadline_dashboard(principal.workspace_id)


@router.get("/boq-defect-summary")
def boq_defect_summary(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).boq_defect_summary(principal.workspace_id)


@router.post("/reports/export")
def export_report(
    request: Request,
    format: str,
    filter: str = "all",
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        result = _service(request, session).export_report(principal.workspace_id, filter, format)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return Response(
        content=result["content"],
        media_type=result["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )


@router.post("/plan")
def plan_dashboard(
    body: PlanQueryBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    identity = {
        "user_id": str(principal.user_id),
        "workspace_id": str(principal.workspace_id),
        "role": principal.role,
        "is_superadmin": getattr(principal, "is_superadmin", False),
    }
    return _service(request, session).plan_dashboard(
        principal.workspace_id,
        body.opportunity_id,
        body.query,
        identity=identity,
        agent=PlanDashboardAgent(),
    )
