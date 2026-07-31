"""Transfer an express ephemeral workspace to a real user (TS-214)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import Workspace, WorkspaceMember


def claim_express_workspace(session: Session, workspace_id: uuid.UUID | str, user_id) -> dict:
    workspace_id = uuid.UUID(str(workspace_id))
    user_id = uuid.UUID(str(user_id))
    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        raise ValueError("workspace_not_found")

    existing = session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if existing is None:
        session.add(WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role="owner"))
    else:
        existing.role = "owner"

    workspace.owner_id = user_id
    if workspace.name.startswith("express-"):
        workspace.name = f"Imported tender {workspace_id.hex[:8]}"
    session.commit()
    return {"workspace_id": str(workspace_id), "user_id": str(user_id)}
