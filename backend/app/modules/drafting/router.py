from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.drafting.service import DraftingError, DraftingService

router = APIRouter()

_STATUS = {
    "no_accepted_findings": 409,
    "bad_kind": 400,
    "findings_unavailable": 503,
    "review_pending": 409,
}


def _service(request: Request, session: Session) -> DraftingService:
    reg = request.app.state.ctx.registry
    return DraftingService(
        session,
        store_factory=reg.get("findings.store_factory"),
        loader=reg.get("rulepacks.loader"),
    )


class GenerateBody(BaseModel):
    kind: str  # clarification_letter | assumptions_register


def _artifact_json(a) -> dict:
    return {
        "id": str(a.id),
        "kind": a.kind,
        "version": a.version,
        "status": a.status,
        "body": a.body,
    }


@router.post("/opportunities/{opportunity_id}/artifacts")
def generate(
    opportunity_id: str,
    body: GenerateBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    # resolve the opportunity title for the artifact header (best-effort)
    reg = request.app.state.ctx.registry
    title = ""
    ing = reg.get("ingestion.service_factory")
    if ing:
        opp = ing(session).get_opportunity(principal.org_id, opportunity_id)
        title = opp.title if opp else ""
    try:
        artifact = _service(request, session).generate(
            principal.org_id, opportunity_id, body.kind, title
        )
    except DraftingError as exc:
        raise HTTPException(_STATUS.get(exc.code, 400), exc.code) from exc
    return _artifact_json(artifact)


@router.get("/opportunities/{opportunity_id}/artifacts")
def list_artifacts(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    arts = _service(request, session).list(principal.org_id, opportunity_id)
    return {"artifacts": [_artifact_json(a) for a in arts]}


@router.get("/artifacts/{artifact_id}")
def get_artifact(
    artifact_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    a = _service(request, session).get(principal.org_id, artifact_id)
    if not a:
        raise HTTPException(404, "not_found")
    return _artifact_json(a)
