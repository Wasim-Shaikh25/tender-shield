"""OrgStandardsService — CRUD for a firm's custom notice standard.

Owns the org_notice_standards table. Publishes the stored standard as plain
dicts (the notice-category shape) so consumers — the baseline module — merge it
without importing this module (CLAUDE.md §2)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.standards.models import OrgNoticeStandard

MODES = {"prevail", "side_by_side"}


class NoticeCategoryIn(BaseModel):
    """Incoming category shape (mirrors a rule-pack NoticeCategory; validated at
    the API boundary so stored org data stays well-formed)."""

    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    typical_days: int | None = Field(default=None, ge=0)
    expected: bool = False
    keywords: list[str] = Field(default_factory=list)
    note: str | None = None


class StandardsError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class OrgStandardsService:
    def __init__(self, session: Session):
        self.s = session

    def _row(self, org_id) -> OrgNoticeStandard | None:
        return self.s.scalar(
            select(OrgNoticeStandard).where(
                OrgNoticeStandard.org_id == uuid.UUID(str(org_id))
            )
        )

    def get_notice(self, org_id) -> dict | None:
        """The org's custom notice standard as a plain dict, or None if unset.
        This is the shape the baseline merge consumes."""
        row = self._row(org_id)
        if row is None:
            return None
        return {"mode": row.mode, "categories": list(row.categories)}

    def set_notice(
        self,
        org_id,
        *,
        mode: Literal["prevail", "side_by_side"],
        categories: list[dict],
        actor=None,
    ) -> dict:
        if mode not in MODES:
            raise StandardsError("bad_mode")
        try:
            clean = [NoticeCategoryIn.model_validate(c).model_dump() for c in categories]
        except ValidationError as exc:
            raise StandardsError("bad_categories") from exc
        keys = [c["key"] for c in clean]
        if len(keys) != len(set(keys)):
            raise StandardsError("duplicate_keys")

        row = self._row(org_id)
        if row is None:
            row = OrgNoticeStandard(org_id=uuid.UUID(str(org_id)))
            self.s.add(row)
        row.mode = mode
        row.categories = clean
        row.updated_by = uuid.UUID(str(actor)) if actor else None
        self.s.commit()
        return {"mode": row.mode, "categories": list(row.categories)}

    def clear_notice(self, org_id) -> None:
        row = self._row(org_id)
        if row is not None:
            self.s.delete(row)
            self.s.commit()
