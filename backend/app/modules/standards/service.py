"""WorkspaceStandardsService — CRUD for a firm's custom notice standard.

Owns the workspace_notice_standards table. Publishes the stored standard as plain
dicts (the notice-category shape) so consumers — the baseline module — merge it
without importing this module (CLAUDE.md §2).
"""

from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.standards.models import WorkspaceCommercialStandard, WorkspaceNoticeStandard

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


class WorkspaceStandardsService:
    def __init__(self, session: Session):
        self.s = session

    def _row(self, workspace_id) -> WorkspaceNoticeStandard | None:
        return self.s.scalar(
            select(WorkspaceNoticeStandard).where(
                WorkspaceNoticeStandard.workspace_id == uuid.UUID(str(workspace_id))
            )
        )

    def get_notice(self, workspace_id) -> dict | None:
        """The workspace's custom notice standard as a plain dict, or None if unset.
        This is the shape the baseline merge consumes."""
        row = self._row(workspace_id)
        if row is None:
            return None
        return {"mode": row.mode, "categories": list(row.categories)}

    def set_notice(
        self,
        workspace_id,
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

        row = self._row(workspace_id)
        if row is None:
            row = WorkspaceNoticeStandard(workspace_id=uuid.UUID(str(workspace_id)))
            self.s.add(row)
        row.mode = mode
        row.categories = clean
        row.updated_by = uuid.UUID(str(actor)) if actor else None
        self.s.commit()
        return {"mode": row.mode, "categories": list(row.categories)}

    def clear_notice(self, workspace_id) -> None:
        row = self._row(workspace_id)
        if row is not None:
            self.s.delete(row)
            self.s.commit()


# ---- commercial standards (policy thresholds) ----

_OPERATORS = {"gt", "gte", "lt", "lte"}
_UNITS = {"percent", "days", "amount"}


class PolicyBody(BaseModel):
    key: str = ""
    label: str = Field(min_length=1)
    operator: str = Field(default="gt")
    threshold: float = Field(ge=0)
    unit: str = Field(default="percent")
    applies_to: list[str] = Field(default_factory=list)
    note: str | None = None


class WorkspaceCommercialStandardsService:
    def __init__(self, session: Session):
        self.s = session

    def list_policies(self, workspace_id) -> list[dict]:
        rows = self.s.scalars(
            select(WorkspaceCommercialStandard).where(
                WorkspaceCommercialStandard.workspace_id == uuid.UUID(str(workspace_id))
            )
        )
        return [_policy_json(r) for r in rows]

    def set_policy(self, workspace_id, *, policy: dict, actor=None) -> dict:
        clean = PolicyBody.model_validate(policy).model_dump()
        if clean["operator"] not in _OPERATORS:
            raise StandardsError("bad_operator")
        if clean["unit"] not in _UNITS:
            raise StandardsError("bad_unit")
        if not clean.get("key"):
            raise StandardsError("missing_key")
        existing = self.s.scalar(
            select(WorkspaceCommercialStandard).where(
                WorkspaceCommercialStandard.workspace_id == uuid.UUID(str(workspace_id)),
                WorkspaceCommercialStandard.key == clean["key"],
            )
        )
        if existing:
            row = existing
        else:
            row = WorkspaceCommercialStandard(
                workspace_id=uuid.UUID(str(workspace_id)), key=clean["key"]
            )
            self.s.add(row)
        row.label = clean["label"]
        row.operator = clean["operator"]
        row.threshold = clean["threshold"]
        row.unit = clean["unit"]
        row.applies_to = list(clean["applies_to"])
        row.note = clean.get("note")
        row.updated_by = uuid.UUID(str(actor)) if actor else None
        self.s.commit()
        return _policy_json(row)

    def delete_policy(self, workspace_id, key: str) -> bool:
        row = self.s.scalar(
            select(WorkspaceCommercialStandard).where(
                WorkspaceCommercialStandard.workspace_id == uuid.UUID(str(workspace_id)),
                WorkspaceCommercialStandard.key == key,
            )
        )
        if row is None:
            return False
        self.s.delete(row)
        self.s.commit()
        return True

    def check_violations(self, workspace_id, findings: list[dict]) -> list[dict]:
        """Return violation dicts for findings that breach an org policy."""
        policies = self.list_policies(workspace_id)
        violations = []
        for f in findings:
            text = " ".join(
                filter(
                    None,
                    [f.get("title", ""), f.get("detail", ""), f.get("source_quote", "")],
                )
            ).lower()
            for p in policies:
                if p["applies_to"] and not any(kw.lower() in text for kw in p["applies_to"]):
                    continue
                value = _extract_number(f, p["unit"])
                if value is None:
                    continue
                if _compare(value, p["operator"], p["threshold"]):
                    violations.append(
                        {
                            "policy_key": p["key"],
                            "policy_label": p["label"],
                            "value": value,
                            "threshold": p["threshold"],
                            "operator": p["operator"],
                            "finding": f,
                        }
                    )
        return violations


def _policy_json(r: WorkspaceCommercialStandard) -> dict:
    return {
        "id": str(r.id),
        "key": r.key,
        "label": r.label,
        "operator": r.operator,
        "threshold": float(r.threshold) if r.threshold is not None else None,
        "unit": r.unit,
        "applies_to": list(r.applies_to or []),
        "note": r.note,
    }


_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_DAYS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*days?")
_AMOUNT_RE = re.compile(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)


def _extract_number(finding: dict, unit: str) -> float | None:
    text = " ".join(filter(None, [finding.get("source_quote", ""), finding.get("detail", "")]))
    if unit == "percent":
        m = _PERCENT_RE.search(text)
    elif unit == "days":
        m = _DAYS_RE.search(text)
    elif unit == "amount":
        m = _AMOUNT_RE.search(text)
    else:
        return None
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _compare(value: float, operator: str, threshold: float) -> bool:
    if operator == "gt":
        return value > threshold
    if operator == "gte":
        return value >= threshold
    if operator == "lt":
        return value < threshold
    if operator == "lte":
        return value <= threshold
    return False
