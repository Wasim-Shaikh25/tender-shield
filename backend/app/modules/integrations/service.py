"""Integration service (TS-281–TS-287)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.integrations.adapters import ADAPTER_REGISTRY, BaseAdapter, ScheduleAdapter
from app.modules.integrations.models import (
    IntegrationCostLine,
    IntegrationDocument,
    IntegrationEvent,
    IntegrationScheduleActivity,
    IntegrationSource,
    IntegrationSyncJob,
)


class IntegrationsError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class IntegrationsService:
    def __init__(
        self,
        session: Session,
        *,
        ingestion_factory: Callable[[Session], object] | None = None,
        change_factory: Callable[[Session], object] | None = None,
        publish: Callable[[str, dict], Any] | None = None,
    ) -> None:
        self.s = session
        self._ingestion_factory = ingestion_factory
        self._change_factory = change_factory
        self._publish = publish or (lambda event, payload: None)

    def _ingestion(self):
        if self._ingestion_factory is None:
            raise IntegrationsError("ingestion_unavailable")
        return self._ingestion_factory(self.s)

    def _change(self):
        if self._change_factory is None:
            raise IntegrationsError("change_unavailable")
        return self._change_factory(self.s)

    def create_source(
        self,
        workspace_id,
        *,
        adapter_kind: str,
        name: str,
        created_by,
        opportunity_id: str | None = None,
        config: dict | None = None,
        rate_limit: int | None = None,
    ) -> IntegrationSource:
        if adapter_kind not in ADAPTER_REGISTRY:
            raise IntegrationsError("unknown_adapter")
        source = IntegrationSource(
            workspace_id=uuid.UUID(str(workspace_id)),
            opportunity_id=uuid.UUID(str(opportunity_id)) if opportunity_id else None,
            adapter_kind=adapter_kind,
            name=name,
            config=config or {},
            rate_limit_calls_per_minute=rate_limit,
            created_by=uuid.UUID(str(created_by)),
        )
        self.s.add(source)
        self.s.commit()
        self.s.refresh(source)
        return source

    def list_sources(self, workspace_id) -> list[IntegrationSource]:
        return list(
            self.s.scalars(
                select(IntegrationSource).where(
                    IntegrationSource.workspace_id == uuid.UUID(str(workspace_id))
                )
            )
        )

    def _get_source(self, workspace_id, source_id) -> IntegrationSource:
        row = self.s.scalar(
            select(IntegrationSource).where(
                IntegrationSource.id == uuid.UUID(str(source_id)),
                IntegrationSource.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )
        if row is None:
            raise IntegrationsError("source_not_found")
        return row

    def import_from_source(
        self,
        workspace_id,
        source_id,
        user_id,
        payload: dict,
    ) -> dict:
        source = self._get_source(workspace_id, source_id)
        adapter_cls = ADAPTER_REGISTRY.get(source.adapter_kind)
        if adapter_cls is None:
            raise IntegrationsError("unknown_adapter")
        adapter: BaseAdapter = adapter_cls()
        job = IntegrationSyncJob(
            workspace_id=uuid.UUID(str(workspace_id)),
            source_id=source.id,
            status="running",
            created_by=uuid.UUID(str(user_id)),
        )
        self.s.add(job)
        self.s.commit()
        self._publish(
            "integrations.import_started",
            {"workspace_id": str(workspace_id), "source_id": str(source_id), "job_id": str(job.id)},
        )

        try:
            result = adapter.normalize(
                payload,
                workspace_id=source.workspace_id,
                source_id=source.id,
                user_id=uuid.UUID(str(user_id)),
                opportunity_id=source.opportunity_id,
            )
            imported = self._persist(workspace_id, source, result, user_id)
            job.status = "completed"
            job.records_imported = (
                imported["documents"]
                + imported["events"]
                + imported["cost_lines"]
                + imported["activities"]
            )
            job.completed_at = datetime.now(UTC)
            self.s.commit()
            self._publish(
                "integrations.import_completed",
                {
                    "workspace_id": str(workspace_id),
                    "source_id": str(source_id),
                    "job_id": str(job.id),
                },
            )
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)
            job.completed_at = datetime.now(UTC)
            self.s.commit()
            self._publish(
                "integrations.import_failed",
                {
                    "workspace_id": str(workspace_id),
                    "source_id": str(source_id),
                    "job_id": str(job.id),
                    "error": str(exc),
                },
            )
            raise IntegrationsError("import_failed") from exc

        return self._job_dict(job, result)

    def _persist(self, workspace_id, source, result, user_id) -> dict:
        counts = {"documents": 0, "events": 0, "cost_lines": 0, "activities": 0}
        ws = source.workspace_id
        uid = uuid.UUID(str(user_id))

        # Documents
        for doc in result.get("documents") or []:
            existing = self.s.scalar(
                select(IntegrationDocument).where(
                    IntegrationDocument.source_id == source.id,
                    IntegrationDocument.source_native_id == doc["source_native_id"],
                )
            )
            if existing:
                existing.last_modified_at = doc.get("last_modified_at")
                existing.source_metadata = doc.get("metadata")
                existing.sample_text = doc.get("sample_text", "")[:4000]
            else:
                created_doc = None
                if source.opportunity_id is not None:
                    try:
                        created_doc = self._ingestion().register_document(
                            ws,
                            source.opportunity_id,
                            doc["filename"],
                            doc.get("sample_text", ""),
                            mime_type=doc.get("mime_type"),
                            uploaded_by=uid,
                        )
                    except Exception as exc:
                        result.setdefault("errors", []).append(f"ingestion: {exc}")
                row = IntegrationDocument(
                    workspace_id=ws,
                    source_id=source.id,
                    source_native_id=doc["source_native_id"],
                    document_id=uuid.UUID(str(created_doc.id)) if created_doc else None,
                    filename=doc["filename"],
                    mime_type=doc.get("mime_type"),
                    source_path=doc.get("source_path"),
                    last_modified_at=doc.get("last_modified_at"),
                    source_metadata=doc.get("metadata"),
                )
                self.s.add(row)
            counts["documents"] += 1

        # Change events
        for event in result.get("events") or []:
            existing = self.s.scalar(
                select(IntegrationEvent).where(
                    IntegrationEvent.source_id == source.id,
                    IntegrationEvent.source_native_id == event["source_native_id"],
                )
            )
            if existing:
                existing.title = event.get("title")
                existing.occurred_at = event.get("occurred_at")
                existing.source_metadata = event.get("metadata")
            else:
                change_event_id = None
                if source.opportunity_id is not None and self._change_factory:
                    try:
                        source_quote = event.get("title") or "Imported from integration"
                        created = self._change().create_manual_event(
                            ws,
                            source.opportunity_id,
                            title=event.get("title") or "Imported event",
                            reason="other",
                            confidence_band="medium",
                            sources=[
                                {
                                    "source_quote": source_quote[:200],
                                    "source_page": 0,
                                }
                            ],
                            created_by=uid,
                        )
                        change_event_id = uuid.UUID(str(created["id"]))
                    except Exception as exc:
                        result.setdefault("errors", []).append(f"change: {exc}")
                row = IntegrationEvent(
                    workspace_id=ws,
                    source_id=source.id,
                    source_native_id=event["source_native_id"],
                    change_event_id=change_event_id,
                    kind=event.get("kind", "other"),
                    title=event.get("title"),
                    occurred_at=event.get("occurred_at"),
                    source_metadata=event.get("metadata"),
                )
                self.s.add(row)
            counts["events"] += 1

        # Cost lines
        for line in result.get("cost_lines") or []:
            existing = self.s.scalar(
                select(IntegrationCostLine).where(
                    IntegrationCostLine.source_id == source.id,
                    IntegrationCostLine.source_native_id == line.get("source_native_id"),
                )
            )
            if existing:
                existing.committed_cost_minor = line.get("committed_cost_minor")
                existing.certified_value_minor = line.get("certified_value_minor")
                existing.description = line.get("description")
            else:
                row = IntegrationCostLine(
                    workspace_id=ws,
                    source_id=source.id,
                    opportunity_id=line.get("opportunity_id"),
                    source_native_id=line.get("source_native_id"),
                    cost_code=line["cost_code"],
                    description=line.get("description"),
                    committed_cost_minor=line.get("committed_cost_minor"),
                    certified_value_minor=line.get("certified_value_minor"),
                    currency=line.get("currency", "INR"),
                    source_metadata=line.get("metadata"),
                )
                self.s.add(row)
            counts["cost_lines"] += 1

        # Schedule activities
        for act in result.get("activities") or []:
            existing = self.s.scalar(
                select(IntegrationScheduleActivity).where(
                    IntegrationScheduleActivity.source_id == source.id,
                    IntegrationScheduleActivity.source_native_id == act["source_native_id"],
                )
            )
            if existing:
                existing.name = act.get("name")
                existing.start_date = act.get("start_date")
                existing.finish_date = act.get("finish_date")
                existing.duration_days = act.get("duration_days")
                existing.source_metadata = act.get("metadata")
            else:
                row = IntegrationScheduleActivity(
                    workspace_id=ws,
                    opportunity_id=source.opportunity_id,
                    source_id=source.id,
                    source_native_id=act["source_native_id"],
                    name=act.get("name", ""),
                    start_date=act.get("start_date"),
                    finish_date=act.get("finish_date"),
                    duration_days=act.get("duration_days"),
                    predecessors=act.get("predecessors"),
                    linked_change_event_ids=act.get("linked_change_event_ids"),
                    source_metadata=act.get("metadata"),
                )
                self.s.add(row)
            counts["activities"] += 1

        self.s.commit()
        return counts

    def list_jobs(self, workspace_id, source_id) -> list[dict]:
        rows = self.s.scalars(
            select(IntegrationSyncJob).where(
                IntegrationSyncJob.workspace_id == uuid.UUID(str(workspace_id)),
                IntegrationSyncJob.source_id == uuid.UUID(str(source_id)),
            ).order_by(IntegrationSyncJob.started_at.desc())
        ).all()
        return [self._job_dict(row, {}) for row in rows]

    def list_documents(self, workspace_id, source_id) -> list[dict]:
        rows = self.s.scalars(
            select(IntegrationDocument).where(
                IntegrationDocument.workspace_id == uuid.UUID(str(workspace_id)),
                IntegrationDocument.source_id == uuid.UUID(str(source_id)),
            )
        ).all()
        return [self._document_dict(row) for row in rows]

    def list_events(self, workspace_id, source_id) -> list[dict]:
        rows = self.s.scalars(
            select(IntegrationEvent).where(
                IntegrationEvent.workspace_id == uuid.UUID(str(workspace_id)),
                IntegrationEvent.source_id == uuid.UUID(str(source_id)),
            )
        ).all()
        return [self._event_dict(row) for row in rows]

    def import_schedule(
        self,
        workspace_id,
        user_id,
        opportunity_id,
        payload: dict,
        source_id: str | None = None,
    ) -> dict:
        adapter = ScheduleAdapter()
        result = adapter.normalize(
            payload,
            workspace_id=uuid.UUID(str(workspace_id)),
            source_id=uuid.UUID(str(source_id)) if source_id else uuid.uuid4(),
            user_id=uuid.UUID(str(user_id)),
            opportunity_id=uuid.UUID(str(opportunity_id)) if opportunity_id else None,
        )
        ws = uuid.UUID(str(workspace_id))
        oid = uuid.UUID(str(opportunity_id))
        sid = uuid.UUID(str(source_id)) if source_id else None
        counts = 0
        for act in result.get("activities") or []:
            row = IntegrationScheduleActivity(
                workspace_id=ws,
                opportunity_id=oid,
                source_id=sid,
                source_native_id=act["source_native_id"],
                name=act.get("name", ""),
                start_date=act.get("start_date"),
                finish_date=act.get("finish_date"),
                duration_days=act.get("duration_days"),
                predecessors=act.get("predecessors"),
                linked_change_event_ids=act.get("linked_change_event_ids"),
                source_metadata=act.get("metadata"),
            )
            self.s.add(row)
            counts += 1
        self.s.commit()
        return {"activities_imported": counts}

    def list_schedule_activities(self, workspace_id, opportunity_id) -> list[dict]:
        rows = self.s.scalars(
            select(IntegrationScheduleActivity).where(
                IntegrationScheduleActivity.workspace_id == uuid.UUID(str(workspace_id)),
                IntegrationScheduleActivity.opportunity_id == uuid.UUID(str(opportunity_id)),
            ).order_by(IntegrationScheduleActivity.start_date)
        ).all()
        return [self._activity_dict(row) for row in rows]

    def snapshot_schedule(self, workspace_id, opportunity_id, user_id) -> dict:
        ws = uuid.UUID(str(workspace_id))
        oid = uuid.UUID(str(opportunity_id))
        rows = self.s.scalars(
            select(IntegrationScheduleActivity).where(
                IntegrationScheduleActivity.workspace_id == ws,
                IntegrationScheduleActivity.opportunity_id == oid,
            )
        ).all()
        snapshot_at = datetime.now(UTC)
        for row in rows:
            row.snapshot_at = snapshot_at
        self.s.commit()
        return {"snapshot_at": snapshot_at.isoformat(), "activities": len(rows)}

    def _job_dict(self, row, result) -> dict:
        return {
            "id": str(row.id),
            "source_id": str(row.source_id),
            "status": row.status,
            "records_imported": row.records_imported,
            "records_skipped": row.records_skipped,
            "records_failed": row.records_failed,
            "error_message": row.error_message,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "result": result,
        }

    def _source_dict(self, row) -> dict:
        return {
            "id": str(row.id),
            "adapter_kind": row.adapter_kind,
            "name": row.name,
            "opportunity_id": str(row.opportunity_id) if row.opportunity_id else None,
            "status": row.status,
            "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def _document_dict(self, row) -> dict:
        return {
            "id": str(row.id),
            "source_native_id": row.source_native_id,
            "document_id": str(row.document_id) if row.document_id else None,
            "filename": row.filename,
            "mime_type": row.mime_type,
            "source_path": row.source_path,
            "last_modified_at": row.last_modified_at.isoformat() if row.last_modified_at else None,
        }

    def _event_dict(self, row) -> dict:
        return {
            "id": str(row.id),
            "source_native_id": row.source_native_id,
            "change_event_id": str(row.change_event_id) if row.change_event_id else None,
            "kind": row.kind,
            "title": row.title,
            "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
        }

    def _activity_dict(self, row) -> dict:
        return {
            "id": str(row.id),
            "source_native_id": row.source_native_id,
            "name": row.name,
            "start_date": row.start_date.isoformat() if row.start_date else None,
            "finish_date": row.finish_date.isoformat() if row.finish_date else None,
            "duration_days": row.duration_days,
            "predecessors": row.predecessors,
            "linked_change_event_ids": row.linked_change_event_ids,
            "snapshot_at": row.snapshot_at.isoformat() if row.snapshot_at else None,
        }
