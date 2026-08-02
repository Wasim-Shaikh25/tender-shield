"""Governance service (TS-332, TS-340)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.governance.models import WorkspaceDataGovernance

logger = logging.getLogger(__name__)


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
        ingestion_apply: Callable[..., dict] | None = None,
        review_factory: Callable[..., Any] | None = None,
        storage: Any | None = None,
        settings: Settings | None = None,
        publish: Callable[[str, dict], Any] | None = None,
    ) -> None:
        self.s = session
        self._ingestion_retention = ingestion_retention
        self._ingestion_apply = ingestion_apply
        self._review_factory = review_factory
        self._storage = storage
        self._settings = settings
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
        return self._ingestion_retention(self.s, workspace_id, retention_days)

    async def run_retention_job(self, now: datetime | None = None) -> dict:
        """Execute workspace data-retention policy for all configured workspaces.

        The job is idempotent and safe to rerun: each candidate is only advanced
        to the next lifecycle stage when its cutoff is crossed.
        """
        if self._settings is None or not self._settings.retention_job_enabled:
            return {"enabled": False, "archived": 0, "soft_deleted": 0, "hard_deleted": 0}

        if self._ingestion_retention is None or self._ingestion_apply is None:
            logger.warning("retention job skipped: ingestion capabilities unavailable")
            return {"enabled": True, "error": "ingestion_unavailable"}

        now = now or datetime.now(UTC)
        grace = timedelta(days=self._settings.retention_grace_days)
        hard_delete_cutoff = now - grace

        rows = self.s.scalars(
            select(WorkspaceDataGovernance).where(
                WorkspaceDataGovernance.retention_days.is_not(None),
                WorkspaceDataGovernance.legal_hold.is_(False),
            )
        ).all()

        archived = 0
        soft_deleted = 0
        hard_deleted = 0

        for settings_row in rows:
            ws_id = str(settings_row.workspace_id)
            retention_days = settings_row.retention_days
            archive_after_days = settings_row.archive_after_days
            retention_cutoff = now - timedelta(days=retention_days)

            archive_cutoff = None
            if archive_after_days is not None and archive_after_days < retention_days:
                archive_cutoff = now - timedelta(days=archive_after_days)

            # Archive pass: documents older than archive_after_days but still
            # within the retention window.
            if archive_cutoff is not None:
                archive_candidates = self._ingestion_retention(self.s, ws_id, archive_after_days)
                for candidate in archive_candidates:
                    if candidate.get("archived_at") or candidate.get("deleted_at"):
                        continue
                    created_at = self._parse_iso(candidate.get("created_at"))
                    if created_at is None or created_at < retention_cutoff:
                        continue
                    self._ingestion_apply(self.s, ws_id, candidate["id"], "archive")
                    self._audit(ws_id, "governance.document_archived", candidate["id"], {
                        "filename": candidate.get("filename"),
                        "kind": candidate.get("kind"),
                    })
                    archived += 1

            # Retention / deletion pass.
            delete_candidates = self._ingestion_retention(self.s, ws_id, retention_days)
            for candidate in delete_candidates:
                deleted_at = self._parse_iso(candidate.get("deleted_at"))
                if deleted_at is not None and deleted_at < hard_delete_cutoff:
                    result = self._ingestion_apply(self.s, ws_id, candidate["id"], "hard_delete")
                    if result.get("s3_key") and self._storage is not None:
                        try:
                            await self._storage.delete(result["s3_key"])
                        except Exception:
                            logger.exception("failed to delete storage object %s", result["s3_key"])
                    self._audit(ws_id, "governance.document_hard_deleted", candidate["id"], {
                        "filename": candidate.get("filename"),
                        "kind": candidate.get("kind"),
                        "s3_key": result.get("s3_key"),
                    })
                    hard_deleted += 1
                elif deleted_at is None:
                    self._ingestion_apply(self.s, ws_id, candidate["id"], "soft_delete")
                    self._audit(ws_id, "governance.document_soft_deleted", candidate["id"], {
                        "filename": candidate.get("filename"),
                        "kind": candidate.get("kind"),
                    })
                    soft_deleted += 1

        return {
            "enabled": True,
            "workspaces_scanned": len(rows),
            "archived": archived,
            "soft_deleted": soft_deleted,
            "hard_deleted": hard_deleted,
        }

    def _audit(self, workspace_id: str, action: str, object_id: str, detail: dict) -> None:
        if self._review_factory is None:
            return
        try:
            svc = self._review_factory(self.s)
            svc.audit(
                workspace_id,
                actor=None,
                action=action,
                object_type="document",
                object_id=object_id,
                detail=detail,
            )
            self.s.commit()
        except Exception:
            logger.exception("retention audit log failed for %s", action)

    @staticmethod
    def _parse_iso(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

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
