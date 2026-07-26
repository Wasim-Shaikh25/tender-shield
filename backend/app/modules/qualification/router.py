from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.qualification.service import QualificationService

router = APIRouter()


def _service(request: Request, session: Session) -> QualificationService:
    reg = request.app.state.ctx.registry
    return QualificationService(
        session,
        ingestion_factory=reg.get("ingestion.service_factory"),
        store_factory=reg.get("findings.store_factory"),
    )


def _row_json(c) -> dict:
    return {
        "key": c.key,
        "label": c.label,
        "status": c.status,
        "evidence": c.evidence,
        "source_page": c.source_page,
        "source_quote": c.source_quote,
        "action_required": c.action_required,
    }


@router.get("/opportunities/{opportunity_id}")
def get_matrix(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    rows = _service(request, session).build_matrix(principal.workspace_id, opportunity_id)
    return {"status": _summary(rows), "criteria": [_row_json(r) for r in rows]}


@router.post("/opportunities/{opportunity_id}")
def run_matrix(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    rows = _service(request, session).run_opportunity(principal.workspace_id, opportunity_id)
    return {"status": _summary(rows), "criteria": [_row_json(r) for r in rows]}


def _summary(rows) -> str:
    if any(r.status == "not_met" for r in rows):
        return "not_eligible"
    if any(r.status == "unknown" for r in rows):
        return "needs_review"
    return "eligible"
