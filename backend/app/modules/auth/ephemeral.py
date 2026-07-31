"""Ephemeral workspaces for the Express pay-per-report lane (TS-209).

Creates real `workspaces` rows backed by a dedicated system user so Express
sessions reuse the existing workspace-scoped isolation path without inventing a
parallel tenant model.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import User, Workspace, WorkspaceMember

EXPRESS_SYSTEM_EMAIL = "express-system@internal.tendershield.local"
EXPRESS_SYSTEM_PHONE = "+910000000000"


def ensure_express_owner(session: Session) -> User:
    user = session.scalar(select(User).where(User.email == EXPRESS_SYSTEM_EMAIL))
    if user is not None:
        return user
    from app.modules.auth import security as sec

    user = User(
        email=EXPRESS_SYSTEM_EMAIL,
        phone=EXPRESS_SYSTEM_PHONE,
        password_hash=sec.hash_password(uuid.uuid4().hex),
        org_name="TenderShield Express",
        city="system",
        email_verified=True,
        mobile_verified=True,
        plan="free",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def create_ephemeral_workspace(session: Session, *, label: str = "express") -> uuid.UUID:
    owner = ensure_express_owner(session)
    workspace = Workspace(
        owner_id=owner.id,
        name=f"{label}-{uuid.uuid4().hex[:10]}",
        country="IN",
    )
    session.add(workspace)
    session.flush()
    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role="owner"))
    session.commit()
    return workspace.id
