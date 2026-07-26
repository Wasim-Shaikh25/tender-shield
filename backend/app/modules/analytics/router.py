from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.analytics.service import AnalyticsService

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
    return _service(request, session).accuracy_dashboard(principal.org_id)
