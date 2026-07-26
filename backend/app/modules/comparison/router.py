from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.comparison.service import ComparisonService

router = APIRouter()


def _service(request: Request, session: Session) -> ComparisonService:
    reg = request.app.state.ctx.registry
    factory = reg.get("comparison.service_factory")
    if factory:
        return factory(session)
    return ComparisonService(
        session,
        ingestion_factory=reg.get("ingestion.service_factory"),
        findings_factory=reg.get("findings.store_factory"),
        drafting_factory=reg.get("drafting.service_factory"),
    )


@router.get("/opportunities")
def compare_opportunities(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    rows = _service(request, session).compare(principal.workspace_id)
    return {"opportunities": rows}
