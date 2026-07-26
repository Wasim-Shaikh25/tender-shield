from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.risk.service import RiskService

router = APIRouter()


def _service(request: Request, session: Session) -> RiskService:
    reg = request.app.state.ctx.registry
    return RiskService(
        session,
        ingestion_factory=reg.get("ingestion.service_factory"),
        loader=reg.get("rulepacks.loader"),
        classifier=reg.get("risk.classifier"),
        store_factory=reg.get("findings.store_factory"),
    )


@router.post("/opportunities/{opportunity_id}/run")
def run(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    reg = request.app.state.ctx.registry
    if reg.get("rulepacks.loader") is None or reg.get("ingestion.service_factory") is None:
        raise HTTPException(503, "risk_dependencies_unavailable")
    findings = _service(request, session).run_opportunity(principal.org_id, opportunity_id)
    return {
        "count": len(findings),
        "findings": [
            {
                "category": f.category,
                "severity": f.severity.value,
                "title": f.title,
                "detail": f.detail,
                "source_page": f.source_page,
                "source_quote": f.source_quote,
                "pattern_id": f.pattern_id,
                "explanation": f.explanation,
            }
            for f in findings
        ],
    }
