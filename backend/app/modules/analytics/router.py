from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.analytics.plan_agent import PlanDashboardAgent
from app.modules.analytics.service import AnalyticsError, AnalyticsService


class PlanQueryBody(BaseModel):
    opportunity_id: str = Field(min_length=1)
    query: str = Field(min_length=1)


class SaveSnapshotBody(BaseModel):
    opportunity_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    query: str = Field(min_length=1)
    dashboard: dict


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
        sealed_opportunity_count_fn=reg.get("baseline.sealed_opportunity_count"),
        baseline_activity_metrics_fn=reg.get("review.baseline_activity_metrics"),
    )


@router.get("/accuracy")
def accuracy_dashboard(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    return _service(request, session).accuracy_dashboard(principal.workspace_id)


@router.get("/baseline-adoption")
def baseline_adoption(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    return _service(request, session).baseline_adoption(principal.workspace_id)


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


@router.get("/claim-metrics")
def claim_metrics(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    fn = request.app.state.ctx.registry.get("claims.cycle_metrics")
    if fn is None:
        raise HTTPException(503, "claims metrics unavailable")
    return fn(session, principal.workspace_id, opportunity_id)


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
    try:
        return _service(request, session).plan_dashboard(
            principal.workspace_id,
            body.opportunity_id,
            body.query,
            identity=identity,
            agent=PlanDashboardAgent(),
        )
    except AnalyticsError as exc:
        if str(exc) == "opportunity_not_found":
            raise HTTPException(404, "opportunity_not_found") from exc
        raise HTTPException(400, str(exc)) from exc


@router.get("/plan/templates")
def plan_templates():
    return AnalyticsService.list_plan_templates()


@router.get("/plan/snapshots")
def list_plan_snapshots(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return {
        "snapshots": _service(request, session).list_plan_snapshots(
            principal.workspace_id, principal.user_id
        )
    }


@router.post("/plan/snapshots")
def save_plan_snapshot(
    body: SaveSnapshotBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).save_plan_snapshot(
            principal.workspace_id,
            principal.user_id,
            body.opportunity_id,
            body.title,
            body.query,
            body.dashboard,
        )
    except AnalyticsError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/plan/snapshots/{snapshot_id}")
def get_plan_snapshot(
    snapshot_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        return _service(request, session).get_plan_snapshot(
            principal.workspace_id, principal.user_id, snapshot_id
        )
    except AnalyticsError as exc:
        if str(exc) == "snapshot_not_found":
            raise HTTPException(404, "snapshot_not_found") from exc
        raise HTTPException(400, str(exc)) from exc


@router.delete("/plan/snapshots/{snapshot_id}")
def delete_plan_snapshot(
    snapshot_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        _service(request, session).delete_plan_snapshot(
            principal.workspace_id, principal.user_id, snapshot_id
        )
        return {"ok": True}
    except AnalyticsError as exc:
        if str(exc) == "snapshot_not_found":
            raise HTTPException(404, "snapshot_not_found") from exc
        raise HTTPException(400, str(exc)) from exc


@router.get("/plan/snapshots/{snapshot_id}/export")
def export_plan_snapshot(
    snapshot_id: str,
    format: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    try:
        result = _service(request, session).export_plan_dashboard(
            principal.workspace_id, principal.user_id, snapshot_id, format
        )
    except AnalyticsError as exc:
        if str(exc) == "snapshot_not_found":
            raise HTTPException(404, "snapshot_not_found") from exc
        raise HTTPException(400, str(exc)) from exc
    return Response(
        content=result["content"],
        media_type=result["content_type"],
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )
