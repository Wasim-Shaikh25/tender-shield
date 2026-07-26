"""WorkspaceAdmin — read/update the billing-relevant columns on the workspaces table.

Published as the `auth.workspace_factory` capability so billing (and admin) can
manage plan state without importing auth's models."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import Workspace


class WorkspaceAdmin:
    def __init__(self, session: Session):
        self.s = session

    def get(self, workspace_id) -> Workspace | None:
        return self.s.scalar(select(Workspace).where(Workspace.id == uuid.UUID(str(workspace_id))))

    def mark_free_review_used(self, workspace_id) -> None:
        workspace = self.get(workspace_id)
        if workspace:
            workspace.free_review_used = True
            self.s.commit()

    def set_plan(self, workspace_id, plan: str) -> None:
        workspace = self.get(workspace_id)
        if workspace:
            workspace.plan = plan
            self.s.commit()
