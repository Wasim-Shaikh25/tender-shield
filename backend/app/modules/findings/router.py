from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.core.pagination import PaginationParams, paginated_list_response
from app.modules.findings.store import FindingStore

router = APIRouter()

_SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


@router.get("/opportunities/{opportunity_id}")
def list_findings(
    opportunity_id: str,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    page: PaginationParams = Depends(),
):
    rows = FindingStore(session).list(principal.workspace_id, opportunity_id)
    rows.sort(key=lambda r: _SEV_RANK.get(r.severity, 9))
    items = [
        {
            "id": str(r.id),
            "producer": r.producer,
            "kind": r.kind,
            "category": r.category,
            "severity": r.severity,
            "title": r.title,
            "detail": r.detail,
            "source": r.source,
            "source_page": r.source_page,
            "source_quote": r.source_quote,
            "review_status": r.review_status,
        }
        for r in rows
    ]
    return {"findings": paginated_list_response(items, page, response)}
