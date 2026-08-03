"""Project state dashboard routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.project_state.service import ProjectStateService

router = APIRouter()


def _service(request: Request, session: Session) -> ProjectStateService:
    reg = request.app.state.ctx.registry
    return ProjectStateService(
        session,
        workspace_factory=reg.require("auth.workspace_factory"),
        ingestion_factory=reg.require("ingestion.service_factory"),
        findings_factory=reg.require("findings.store_factory"),
        baseline_factory=reg.get("baseline.service_factory"),
    )


@router.get("/opportunities")
def list_opportunities(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    workspace_id: str | None = None,
    status: str | None = None,
    health: str | None = None,
    jurisdiction: str | None = None,
    min_value: int | None = None,
    max_value: int | None = None,
    deadline_after: str | None = None,
    deadline_before: str | None = None,
):
    return {
        "opportunities": _service(request, session).list_opportunities(
            principal.user_id,
            workspace_id=workspace_id,
            status=status,
            health=health,
            jurisdiction=jurisdiction,
            min_value=min_value,
            max_value=max_value,
            deadline_after=deadline_after,
            deadline_before=deadline_before,
        )
    }


@router.get("/opportunities/{opportunity_id}/state")
def get_opportunity_state(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    svc = _service(request, session)
    # Caller must be a member of the opportunity's workspace; the actual
    # workspace is resolved by the ingestion service below with RLS.
    try:
        return svc.state_for_opportunity(principal.workspace_id, opportunity_id)
    except ValueError as exc:
        if str(exc) == "not_found":
            raise HTTPException(404, "not_found") from exc
        raise


@router.get("/workspaces/me/opportunities/state")
def workspace_summaries(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return {"workspaces": _service(request, session).workspace_summaries(principal.user_id)}
