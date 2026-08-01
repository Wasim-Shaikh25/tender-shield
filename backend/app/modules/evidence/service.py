"""EvidenceService — chain of custody and completeness (TS-254, TS-255)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.evidence.completeness import score_completeness
from app.modules.evidence.models import EvidenceRecord

_RECORD_TYPES = frozenset(
    {
        "site_instruction",
        "photograph",
        "measurement",
        "daily_report",
        "meeting_minutes",
        "correspondence",
        "drawing_revision",
        "other",
    }
)


class EvidenceError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class EvidenceService:
    def __init__(
        self,
        session: Session,
        *,
        change_event_fn: Callable[..., dict] | None = None,
        publish: Callable[[str, dict], int] | None = None,
    ):
        self.s = session
        self._change_event_fn = change_event_fn
        self._publish = publish

    def attach(
        self,
        workspace_id,
        event_id,
        *,
        record_type: str,
        title: str,
        description: str | None = None,
        captured_at: datetime | None = None,
        document_id: str | None = None,
        created_by,
    ) -> dict:
        if record_type not in _RECORD_TYPES:
            raise EvidenceError("bad_record_type")
        if not title.strip():
            raise EvidenceError("bad_request")
        event = self._load_event(workspace_id, event_id)
        when = captured_at or datetime.now(UTC)
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        creator = uuid.UUID(str(created_by))
        row = EvidenceRecord(
            workspace_id=uuid.UUID(str(workspace_id)),
            opportunity_id=uuid.UUID(str(event["opportunity_id"])),
            change_event_id=uuid.UUID(str(event_id)),
            record_type=record_type,
            title=title.strip(),
            description=description,
            captured_at=when,
            document_id=uuid.UUID(str(document_id)) if document_id else None,
            custody_chain=[
                {
                    "user_id": str(creator),
                    "action": "created",
                    "at": when.isoformat(),
                }
            ],
            created_by=creator,
        )
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        if self._publish:
            self._publish(
                "evidence.record_attached",
                {
                    "workspace_id": str(workspace_id),
                    "event_id": str(event_id),
                    "record_id": str(row.id),
                    "record_type": record_type,
                },
            )
        return self._record_dict(row)

    def list_for_event(self, workspace_id, event_id) -> list[dict]:
        self._load_event(workspace_id, event_id)
        rows = self.s.scalars(
            select(EvidenceRecord)
            .where(
                EvidenceRecord.workspace_id == uuid.UUID(str(workspace_id)),
                EvidenceRecord.change_event_id == uuid.UUID(str(event_id)),
            )
            .order_by(EvidenceRecord.captured_at.desc())
        ).all()
        return [self._record_dict(row) for row in rows]

    def get(self, workspace_id, record_id) -> dict:
        row = self.s.scalar(
            select(EvidenceRecord).where(
                EvidenceRecord.id == uuid.UUID(str(record_id)),
                EvidenceRecord.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )
        if row is None:
            raise EvidenceError("not_found")
        return self._record_dict(row)

    def completeness_for_event(self, workspace_id, event_id) -> dict:
        event = self._load_event(workspace_id, event_id)
        rows = self.list_for_event(workspace_id, event_id)
        present = {row["record_type"] for row in rows}
        payload = score_completeness(reason=event.get("reason"), present_types=present)
        payload["record_count"] = len(rows)
        return payload

    def _load_event(self, workspace_id, event_id) -> dict:
        if self._change_event_fn is None:
            raise EvidenceError("change_unavailable")
        try:
            return self._change_event_fn(self.s, workspace_id, event_id)
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code == "not_found":
                raise EvidenceError("not_found") from exc
            raise EvidenceError("change_unavailable") from exc

    def _record_dict(self, row: EvidenceRecord) -> dict:
        return {
            "id": str(row.id),
            "opportunity_id": str(row.opportunity_id),
            "change_event_id": str(row.change_event_id),
            "record_type": row.record_type,
            "title": row.title,
            "description": row.description,
            "captured_at": row.captured_at.isoformat() if row.captured_at else None,
            "document_id": str(row.document_id) if row.document_id else None,
            "custody_chain": row.custody_chain or [],
            "created_by": str(row.created_by),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
