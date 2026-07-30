from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.review.service import ReviewError, ReviewService

router = APIRouter()


def _service(request: Request, session: Session) -> ReviewService:
    reg = request.app.state.ctx.registry
    return ReviewService(session, store_factory=reg.get("findings.store_factory"))


class ReviewBody(BaseModel):
    opportunity_id: str
    decision: str  # accepted | edited | rejected | false_positive | needs_clarification
    note: str | None = None
    review_reason: str | None = None


@router.get("/opportunities/{opportunity_id}/queue")
def queue(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    rows = _service(request, session).queue(principal.workspace_id, opportunity_id)
    return {
        "findings": [
            {
                "id": str(r.id),
                "kind": r.kind,
                "category": r.category,
                "severity": r.severity,
                "title": r.title,
                "review_status": r.review_status,
                "review_note": r.review_note,
                "review_reason": r.review_reason,
                "explanation": r.explanation,
            }
            for r in rows
        ]
    }


@router.post("/findings/{finding_id}")
def review_finding(
    finding_id: str,
    body: ReviewBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("reviewer")),
):
    try:
        row = _service(request, session).review_finding(
            principal.workspace_id,
            finding_id,
            decision=body.decision,
            note=body.note,
            review_reason=body.review_reason,
            reviewer_id=principal.user_id,
            opportunity_id=body.opportunity_id,
        )
    except ReviewError as exc:
        status = 404 if exc.code == "not_found" else 400
        raise HTTPException(status, exc.code) from exc
    return {"id": str(row.id), "review_status": row.review_status}


@router.get("/opportunities/{opportunity_id}/gate")
def gate(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).gate(principal.workspace_id, opportunity_id)


@router.get("/opportunities/{opportunity_id}/audit")
def audit_trail(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("reviewer")),
):
    rows = _service(request, session).audit_trail(principal.workspace_id, opportunity_id)
    return {
        "audit": [
            {
                "id": r.id,
                "action": r.action,
                "object_id": str(r.object_id) if r.object_id else None,
                "at": r.at.isoformat() if r.at else None,
            }
            for r in rows
        ]
    }
