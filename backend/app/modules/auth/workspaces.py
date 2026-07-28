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
        """No commit here — the caller controls the transaction boundary.

        authorize_review (R-004 §A.4) wraps this write together with a
        per-workspace advisory lock and a usage-event write in ONE
        transaction; committing here would end that transaction (and release
        the lock) before the rest of the metering logic runs, defeating the
        race-safety the lock exists for.
        """
        workspace = self.get(workspace_id)
        if workspace:
            workspace.free_review_used = True

    def set_plan(self, workspace_id, plan: str) -> None:
        """No commit here — see mark_free_review_used."""
        workspace = self.get(workspace_id)
        if workspace:
            workspace.plan = plan
