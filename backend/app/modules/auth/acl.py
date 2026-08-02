"""Document-class ACL for workspace role gating (TS-330).

Default policy is permissive: if no ACL row exists for a document class, all
authenticated workspace members may access it. If a row exists, the principal's
role must be at least `min_role`.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, UniqueConstraint, Uuid, select
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, WorkspaceScopedMixin

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class DocumentClassAcl(Base, WorkspaceScopedMixin):
    __tablename__ = "document_class_acls"
    _tablename_ = "document_class_acls"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_class: Mapped[str] = mapped_column(String, nullable=False)
    min_role: Mapped[str] = mapped_column(String, nullable=False, default="viewer")

    __table_args__ = (
        UniqueConstraint("workspace_id", "document_class"),
    )


class AuthAcl:
    ROLE_RANK = {"viewer": 0, "reviewer": 1, "estimator": 2, "admin": 3, "owner": 4}

    def __init__(self, session: Session):
        self.s = session

    def permitted(self, workspace_id, principal_role: str, document_class: str) -> bool:
        if principal_role == "owner" or principal_role == "superadmin":
            return True
        ws = uuid.UUID(str(workspace_id))
        row = self.s.scalar(
            select(DocumentClassAcl).where(
                DocumentClassAcl.workspace_id == ws,
                DocumentClassAcl.document_class == document_class,
            )
        )
        if row is None:
            return True
        return self.ROLE_RANK.get(principal_role, -1) >= self.ROLE_RANK.get(
            row.min_role, 0
        )

    def list_rules(self, workspace_id) -> list[dict]:
        ws = uuid.UUID(str(workspace_id))
        rows = self.s.scalars(
            select(DocumentClassAcl).where(DocumentClassAcl.workspace_id == ws)
        ).all()
        return [
            {
                "id": str(r.id),
                "document_class": r.document_class,
                "min_role": r.min_role,
            }
            for r in rows
        ]

    def set_rule(self, workspace_id, document_class: str, min_role: str) -> dict:
        ws = uuid.UUID(str(workspace_id))
        row = self.s.scalar(
            select(DocumentClassAcl).where(
                DocumentClassAcl.workspace_id == ws,
                DocumentClassAcl.document_class == document_class,
            )
        )
        if row is None:
            row = DocumentClassAcl(
                workspace_id=ws,
                document_class=document_class,
                min_role=min_role,
            )
            self.s.add(row)
        else:
            row.min_role = min_role
        self.s.commit()
        return {
            "id": str(row.id),
            "document_class": row.document_class,
            "min_role": row.min_role,
        }

    def delete_rule(self, workspace_id, document_class: str) -> dict:
        ws = uuid.UUID(str(workspace_id))
        row = self.s.scalar(
            select(DocumentClassAcl).where(
                DocumentClassAcl.workspace_id == ws,
                DocumentClassAcl.document_class == document_class,
            )
        )
        if row is None:
            return {"deleted": False}
        self.s.delete(row)
        self.s.commit()
        return {"deleted": True}
