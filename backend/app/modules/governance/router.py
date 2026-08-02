"""Governance API (TS-332)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import audit as audit_log
from app.core.deps import get_session, require
from app.modules.governance.service import GovernanceError, GovernanceService

router = APIRouter()


class DataGovernanceBody(BaseModel):
    data_region: str | None = Field(default=None, min_length=0)
    retention_days: int | None = Field(default=None, ge=1)
    archive_after_days: int | None = Field(default=None, ge=1)
    legal_hold: bool | None = Field(default=None)
    encryption_at_rest: str | None = Field(default=None)


def _service(request: Request, session: Session) -> GovernanceService:
    reg = request.app.state.ctx.registry
    return GovernanceService(
        session,
        ingestion_retention=reg.get("ingestion.documents_for_retention"),
        publish=request.app.state.ctx.events.publish,
    )


@router.get("/workspaces/{workspace_id}/data-governance")
def get_data_governance(
    workspace_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return _service(request, session).get_settings(workspace_id)
    except GovernanceError as exc:
        raise HTTPException(400, exc.code) from exc


@router.put("/workspaces/{workspace_id}/data-governance")
def update_data_governance(
    workspace_id: str,
    body: DataGovernanceBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        result = _service(request, session).update_settings(
            workspace_id, body.model_dump(exclude_unset=True)
        )
    except GovernanceError as exc:
        raise HTTPException(400, exc.code) from exc
    audit_log.log(
        request,
        session,
        workspace_id=workspace_id,
        actor_user_id=principal.user_id,
        action="governance.settings_updated",
        object_type="workspace",
        object_id=workspace_id,
        detail=result,
    )
    return result


@router.get("/workspaces/{workspace_id}/data-governance/retention-candidates")
def retention_candidates(
    workspace_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return {
            "candidates": _service(request, session).retention_candidates(workspace_id)
        }
    except GovernanceError as exc:
        raise HTTPException(400, exc.code) from exc
