from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.crossref.service import CrossRefService

router = APIRouter()


def _service(request: Request, session: Session) -> CrossRefService:
    reg = request.app.state.ctx.registry
    return CrossRefService(session, ingestion_factory=reg.get("ingestion.service_factory"))


@router.get("/opportunities/{opportunity_id}")
def search(
    opportunity_id: str,
    q: str = "",
    limit: int = 20,
    request: Request = None,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    if not q.strip():
        raise HTTPException(422, "query_required")
    # Avoid unbounded search payloads.
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100
    return {
        "query": q,
        "results": _service(request, session).search(
            principal.workspace_id, opportunity_id, q, limit=limit
        ),
    }


@router.post("/opportunities/{opportunity_id}/diff")
def diff(
    opportunity_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    document_id: str | None = None,
):
    return _service(request, session).diff(principal.workspace_id, opportunity_id, document_id)
