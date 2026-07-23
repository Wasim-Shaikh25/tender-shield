from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.boq.service import BoqRunner

router = APIRouter()


@router.get("")
def boq_status(request: Request) -> dict:
    engine = request.app.state.ctx.registry.get("boq.engine")
    return {
        "engine": "deterministic (zero LLM)",
        "available_checklists": engine.available_checklists() if engine else [],
    }


class RunBody(BaseModel):
    csv: str


@router.post("/opportunities/{opportunity_id}/run")
def run_boq(
    opportunity_id: str,
    body: RunBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    reg = request.app.state.ctx.registry
    engine = reg.get("boq.engine")
    if engine is None:
        raise HTTPException(503, "boq_unavailable")
    runner = BoqRunner(
        session,
        engine=engine,
        store_factory=reg.get("findings.store_factory"),
        ingestion_factory=reg.get("ingestion.service_factory"),
    )
    try:
        findings = runner.run_csv(principal.org_id, opportunity_id, body.csv)
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, f"bad_boq: {exc}") from exc
    return {
        "count": len(findings),
        "findings": [
            {
                "category": f.category,
                "severity": f.severity.value,
                "kind": f.kind.value,
                "title": f.title,
                "detail": f.detail,
            }
            for f in findings
        ],
    }
