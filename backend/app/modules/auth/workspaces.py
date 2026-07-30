"""WorkspaceAdmin — read/update workspace and user billing state.

Published as the `auth.workspace_factory` capability so billing (and admin) can
manage plan state without importing auth's models. Plan and free-review flags are
stored on the user account, not the workspace — a user can create/delete workspaces
without losing their subscription."""

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

    def get_owner(self, workspace_id) -> uuid.UUID | None:
        ws = self.get(workspace_id)
        return ws.owner_id if ws else None

    def list_all_workspaces(self) -> list[dict]:
        return [
            {
                "workspace_id": str(w.id),
                "name": w.name,
                "owner_id": str(w.owner_id),
                "country": w.country,
            }
            for w in self.s.scalars(select(Workspace)).all()
        ]

    def is_paying(self, user_id) -> bool:
        user = self.s.get(User, uuid.UUID(str(user_id)))
        return user is not None and user.plan.lower() in PAID_PLANS

    def get_user(self, user_id) -> dict | None:
        user = self.s.scalar(select(User).where(User.id == uuid.UUID(str(user_id))))
        if user is None:
            return None
        return {
            "id": str(user.id),
            "email": user.email,
            "is_superadmin": user.is_superadmin,
            "plan": user.plan,
            "free_review_used": user.free_review_used,
            "billing_provider": user.billing_provider,
            "billing_settings": user.billing_settings,
        }

    def get_user_plan(self, user_id) -> str | None:
        user = self.s.get(User, uuid.UUID(str(user_id)))
        return user.plan if user else None

    def list_members(self, workspace_id) -> list[dict]:
        rows = self.s.execute(
            select(User.id, User.email)
            .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
            .where(WorkspaceMember.workspace_id == uuid.UUID(str(workspace_id)))
        )
        return [{"user_id": str(r[0]), "email": r[1]} for r in rows]

    def mark_free_review_used(self, user_id, *, used: bool = True, commit: bool = True) -> None:
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if user:
            user.free_review_used = used
            if commit:
                self.s.commit()

    def set_user_plan(self, user_id, plan: str, *, commit: bool = True) -> dict:
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if user is None:
            raise ValueError("no_such_user")
        previous = user.plan
        user.plan = plan
        if commit:
            self.s.commit()
        return {"plan": plan, "previous_plan": previous}

    def get_billing_settings(self, user_id) -> dict:
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if user is None:
            return {}
        return user.billing_settings or {}

    def set_billing_settings(self, user_id, settings: dict, *, commit: bool = True) -> None:
        user = self.s.get(User, uuid.UUID(str(user_id)))
        if user:
            user.billing_settings = settings
            if commit:
                self.s.commit()
