"""WorkspaceAdmin — read/update the billing-relevant columns on the workspaces table.

Published as the `auth.workspace_factory` capability so billing (and admin) can
manage plan state without importing auth's models."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import User, Workspace, WorkspaceMember

PAID_PLANS = {"pro", "enterprise", "paygo", "team"}


class WorkspaceAdmin:
    def __init__(self, session: Session):
        self.s = session

    def get(self, workspace_id) -> Workspace | None:
        return self.s.scalar(select(Workspace).where(Workspace.id == uuid.UUID(str(workspace_id))))

    def list_all_workspaces(self) -> list[dict]:
        return [
            {
                "workspace_id": str(w.id),
                "name": w.name,
                "owner_id": str(w.owner_id),
                "plan": w.plan,
                "country": w.country,
            }
            for w in self.s.scalars(select(Workspace)).all()
        ]

    def is_paying(self, workspace_id) -> bool:
        ws = self.get(workspace_id)
        return ws is not None and ws.plan.lower() in PAID_PLANS

    def get_user(self, user_id) -> dict | None:
        user = self.s.scalar(select(User).where(User.id == uuid.UUID(str(user_id))))
        if user is None:
            return None
        return {"id": str(user.id), "email": user.email, "is_superadmin": user.is_superadmin}

    def list_members(self, workspace_id) -> list[dict]:
        rows = self.s.execute(
            select(User.email)
            .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
            .where(WorkspaceMember.workspace_id == uuid.UUID(str(workspace_id)))
        )
        return [{"email": r[0]} for r in rows]

    def mark_free_review_used(self, workspace_id, *, commit: bool = True) -> None:
        workspace = self.get(workspace_id)
        if workspace:
            workspace.free_review_used = True
            if commit:
                self.s.commit()

    def set_plan(self, workspace_id, plan: str, *, commit: bool = True) -> None:
        workspace = self.get(workspace_id)
        if workspace:
            workspace.plan = plan
            if commit:
                self.s.commit()
