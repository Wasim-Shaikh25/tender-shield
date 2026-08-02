"""Governance service (TS-332)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.governance.models import WorkspaceDataGovernance


class GovernanceError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class GovernanceService:
    def __init__(
        self,
        session: Session,
        *,
        ingestion_retention: Callable[..., list[dict]] | None = None,
        publish: Callable[[str, dict], Any] | None = None,
    ) -> None:
        self.s = session
        self._ingestion_retention = ingestion_retention
        self._publish = publish or (lambda event, payload: None)

    def _default_settings(self, workspace_id) -> WorkspaceDataGovernance:
        ws = uuid.UUID(str(workspace_id))
        row = WorkspaceDataGovernance(workspace_id=ws)
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        return row

    def get_settings(self, workspace_id) -> dict:
        ws = uuid.UUID(str(workspace_id))
        row = self.s.scalar(
            select(WorkspaceDataGovernance).where(
                WorkspaceDataGovernance.workspace_id == ws
            )
        )
        if row is None:
            row = self._default_settings(workspace_id)
        return self._to_dict(row)

    def update_settings(self, workspace_id, fields: dict) -> dict:
        ws = uuid.UUID(str(workspace_id))
        row = self.s.scalar(
            select(WorkspaceDataGovernance).where(
                WorkspaceDataGovernance.workspace_id == ws
            )
        )
        if row is None:
            row = WorkspaceDataGovernance(workspace_id=ws)
            self.s.add(row)
        for key, value in fields.items():
            if hasattr(row, key):
                setattr(row, key, value)
        self.s.commit()
        self.s.refresh(row)
        self._publish(
            "governance.settings_changed",
            {"workspace_id": str(workspace_id), "settings": self._to_dict(row)},
        )
        return self._to_dict(row)

    def retention_candidates(self, workspace_id) -> list[dict]:
        settings = self.get_settings(workspace_id)
        if settings.get("legal_hold"):
            return []
        retention_days = settings.get("retention_days")
        if not retention_days or self._ingestion_retention is None:
            return []
        return self._ingestion_retention(workspace_id, retention_days)

    def _to_dict(self, row: WorkspaceDataGovernance) -> dict:
        return {
            "workspace_id": str(row.workspace_id),
            "data_region": row.data_region,
            "retention_days": row.retention_days,
            "archive_after_days": row.archive_after_days,
            "legal_hold": row.legal_hold,
            "encryption_at_rest": row.encryption_at_rest,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
