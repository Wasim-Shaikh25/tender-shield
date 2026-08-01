"""Workspace approval matrix (TS-239).

Role and monetary limits per commercial action. Missing matrix entries allow
the action (graceful degradation when auth is disabled or unconfigured).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import ApprovalLimit
from app.modules.auth.rbac import ROLE_RANK

ACTIONS = (
    "watchlist_edit",
    "notice_contacts_edit",
    "cost_code_edit",
    "variation_accept",
    "claim_submit",
    "notice_issue",
)


@dataclass(frozen=True)
class ApprovalDecision:
    allowed: bool
    reason: str | None = None


class ApprovalMatrix:
    def __init__(self, session: Session):
        self.s = session

    def list_limits(self, workspace_id) -> list[dict]:
        rows = self.s.scalars(
            select(ApprovalLimit)
            .where(ApprovalLimit.workspace_id == uuid.UUID(str(workspace_id)))
            .order_by(ApprovalLimit.action)
        ).all()
        return [
            {
                "action": row.action,
                "min_role": row.min_role,
                "max_amount_minor": row.max_amount_minor,
            }
            for row in rows
        ]

    def replace_limits(self, workspace_id, limits: list[dict], *, updated_by) -> list[dict]:
        wid = uuid.UUID(str(workspace_id))
        existing = {
            row.action: row
            for row in self.s.scalars(
                select(ApprovalLimit).where(ApprovalLimit.workspace_id == wid)
            ).all()
        }
        seen: set[str] = set()
        for entry in limits:
            action = entry["action"]
            if action not in ACTIONS:
                raise ValueError(f"unknown_action:{action}")
            min_role = entry.get("min_role", "estimator")
            if min_role not in ROLE_RANK:
                raise ValueError(f"bad_role:{min_role}")
            max_amount = entry.get("max_amount_minor")
            row = existing.get(action)
            if row is None:
                row = ApprovalLimit(
                    workspace_id=wid,
                    action=action,
                    min_role=min_role,
                    max_amount_minor=max_amount,
                    updated_by=uuid.UUID(str(updated_by)) if updated_by else None,
                )
                self.s.add(row)
            else:
                row.min_role = min_role
                row.max_amount_minor = max_amount
                row.updated_by = uuid.UUID(str(updated_by)) if updated_by else None
            seen.add(action)
        for action, row in existing.items():
            if action not in seen:
                self.s.delete(row)
        self.s.commit()
        return self.list_limits(workspace_id)

    def check(
        self,
        workspace_id,
        *,
        role: str,
        action: str,
        amount_minor: int = 0,
    ) -> ApprovalDecision:
        row = self.s.scalar(
            select(ApprovalLimit).where(
                ApprovalLimit.workspace_id == uuid.UUID(str(workspace_id)),
                ApprovalLimit.action == action,
            )
        )
        if row is None:
            return ApprovalDecision(True)
        if ROLE_RANK.get(role, -1) < ROLE_RANK.get(row.min_role, 99):
            return ApprovalDecision(False, "role_below_minimum")
        if row.max_amount_minor is not None and amount_minor > row.max_amount_minor:
            return ApprovalDecision(False, "amount_above_limit")
        return ApprovalDecision(True)


def make_checker(session: Session):
    matrix = ApprovalMatrix(session)

    def check(workspace_id, *, role: str, action: str, amount_minor: int = 0) -> ApprovalDecision:
        return matrix.check(
            workspace_id, role=role, action=action, amount_minor=amount_minor
        )

    return check
