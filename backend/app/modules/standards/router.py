from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.standards.service import OrgStandardsService, StandardsError

router = APIRouter()

_ERROR_STATUS = {"bad_mode": 400, "bad_categories": 422, "duplicate_keys": 409}


def _service(session: Session) -> OrgStandardsService:
    return OrgStandardsService(session)


class CategoryBody(BaseModel):
    key: str
    label: str
    typical_days: int | None = None
    expected: bool = False
    keywords: list[str] = []
    note: str | None = None


class NoticeStandardBody(BaseModel):
    mode: str = "prevail"  # prevail | side_by_side
    categories: list[CategoryBody] = []


@router.get("/notice")
def get_notice(
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    std = _service(session).get_notice(principal.org_id)
    return std or {"mode": "prevail", "categories": []}


@router.put("/notice")
def set_notice(
    body: NoticeStandardBody,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        return _service(session).set_notice(
            principal.org_id,
            mode=body.mode,
            categories=[c.model_dump() for c in body.categories],
            actor=principal.user_id,
        )
    except StandardsError as exc:
        raise HTTPException(_ERROR_STATUS.get(exc.code, 400), exc.code) from exc


@router.delete("/notice")
def clear_notice(
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    _service(session).clear_notice(principal.org_id)
    return {"cleared": True}
