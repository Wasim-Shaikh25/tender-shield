"""Integration service (TS-281–TS-287)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.integrations.adapters import ADAPTER_REGISTRY, BaseAdapter, ScheduleAdapter
from app.modules.integrations.connectors import CONNECTOR_REGISTRY
from app.modules.integrations.connectors.dynamic import DynamicRestConnector
from app.modules.integrations.models import (
    DynamicConnectorConfig,
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
        live_connector_polling_enabled: bool = False,
    ) -> None:
        self.s = session
        self._ingestion_factory = ingestion_factory
        self._change_factory = change_factory
        self._publish = publish or (lambda event, payload: None)
        self._live_connector_polling_enabled = live_connector_polling_enabled

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
        if adapter_kind not in ADAPTER_REGISTRY and adapter_kind not in CONNECTOR_REGISTRY:
            raise IntegrationsError("unknown_adapter")
        if opportunity_id:
            opp = self._ingestion().get_opportunity(workspace_id, opportunity_id)
            if opp is None:
                raise IntegrationsError("no_such_opportunity")
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
        if opportunity_id:
            opp = self._ingestion().get_opportunity(workspace_id, opportunity_id)
            if opp is None:
                raise IntegrationsError("no_such_opportunity")
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

    # ---- live CDE/ERP connectors (TS-333) ---------------------------------

    def list_connectors(self) -> list[dict]:
        return [
            {"kind": kind, "name": cls.name, "auth_required": cls.auth_required}
            for kind, cls in sorted(CONNECTOR_REGISTRY.items())
        ]

    def list_adapters(self) -> list[dict]:
        return [
            {"kind": cls.name, "supported_mimetypes": list(cls.supported_mimetypes)}
            for cls in sorted(ADAPTER_REGISTRY.values(), key=lambda c: c.name)
        ]

    def _connector_for_source(self, source: IntegrationSource):
        connector_cls = CONNECTOR_REGISTRY.get(source.adapter_kind)
        if connector_cls is None:
            return None
        return connector_cls()

    def oauth_start(self, workspace_id, source_id: str, redirect_uri: str) -> dict:
        source = self._get_source(workspace_id, source_id)
        connector = self._connector_for_source(source)
        if connector is None:
            raise IntegrationsError("unknown_connector")
        state = f"{source_id}:{uuid.uuid4().hex}"
        config = dict(source.config or {})
        config["oauth_state"] = state
        source.config = config
        self.s.commit()
        url = connector.authorization_url(source, redirect_uri, state)
        if url is None:
            raise IntegrationsError("connector_not_configured")
        return {"authorization_url": url, "state": state}

    def oauth_callback(self, kind: str, code: str, state: str) -> dict:
        try:
            source_id, _ = state.split(":", 1)
        except ValueError:
            raise IntegrationsError("invalid_state") from None
        source = self.s.scalar(
            select(IntegrationSource).where(IntegrationSource.id == uuid.UUID(str(source_id)))
        )
        if source is None or source.adapter_kind != kind:
            raise IntegrationsError("source_not_found")
        config = dict(source.config or {})
        if config.get("oauth_state") != state:
            raise IntegrationsError("invalid_state")
        connector = self._connector_for_source(source)
        if connector is None:
            raise IntegrationsError("unknown_connector")
        token = connector.exchange_code(source, code, "")
        config.update(token)
        config.pop("oauth_state", None)
        source.config = config
        source.status = "authorized"
        self.s.commit()
        self._publish(
            "integrations.oauth_completed",
            {"workspace_id": str(source.workspace_id), "source_id": source_id},
        )
        return {"status": "authorized", "source_id": source_id}

    def poll_source(
        self, workspace_id, source_id: str, user_id
    ) -> dict:
        source = self._get_source(workspace_id, source_id)
        connector = self._connector_for_source(source)
        if connector is None:
            raise IntegrationsError("unknown_connector")
        if not self._live_connector_polling_enabled:
            return {
                "status": "disabled",
                "note": "Live connector polling is disabled by TS_LIVE_CONNECTOR_POLLING_ENABLED.",
            }
        job = IntegrationSyncJob(
            workspace_id=uuid.UUID(str(workspace_id)),
            source_id=source.id,
            status="running",
            created_by=uuid.UUID(str(user_id)),
        )
        self.s.add(job)
        self.s.commit()
        try:
            result = connector.fetch(source)
            imported = self._persist(workspace_id, source, result, user_id)
            job.status = "completed"
            job.records_imported = (
                imported["documents"]
                + imported["events"]
                + imported["cost_lines"]
                + imported["activities"]
            )
            job.completed_at = datetime.now(UTC)
            source.last_synced_at = datetime.now(UTC)
            source.status = "active"
            self.s.commit()
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)
            job.completed_at = datetime.now(UTC)
            self.s.commit()
            raise IntegrationsError("import_failed") from exc
        return self._job_dict(job, result)

    def handle_webhook(self, source_id: str, payload: dict) -> dict:
        source = self.s.scalar(
            select(IntegrationSource).where(
                IntegrationSource.id == uuid.UUID(str(source_id))
            )
        )
        if source is None:
            raise IntegrationsError("source_not_found")
        connector = self._connector_for_source(source)
        if connector is None:
            raise IntegrationsError("unknown_connector")
        self._publish(
            "integrations.webhook_received",
            {"source_id": source_id, "event_count": len(payload.get("events", []))},
        )
        return {"status": "received", "source_id": source_id}

    # ---- dynamic REST connector (TS-334) ----------------------------------

    def _mask_auth(self, config: DynamicConnectorConfig) -> dict[str, Any]:
        auth = dict(config.auth_config or {})
        for key in ("token", "password", "api_key"):
            if key in auth:
                auth[key] = "***"
        return auth

    def _config_dict(self, row: DynamicConnectorConfig, *, mask: bool = True) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "name": row.name,
            "base_url": row.base_url,
            "auth_type": row.auth_type,
            "auth_config": self._mask_auth(row) if mask else (row.auth_config or {}),
            "headers": row.headers or {},
            "pagination": row.pagination or {},
            "mappings": row.mappings or {},
            "enabled": row.enabled,
            "last_tested_at": row.last_tested_at.isoformat() if row.last_tested_at else None,
            "last_test_status": row.last_test_status,
            "workspace_id": str(row.workspace_id),
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def _get_dynamic_config(self, workspace_id, config_id: str) -> DynamicConnectorConfig:
        row = self.s.scalar(
            select(DynamicConnectorConfig).where(
                DynamicConnectorConfig.id == uuid.UUID(str(config_id)),
                DynamicConnectorConfig.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )
        if row is None:
            raise IntegrationsError("dynamic_config_not_found")
        return row

    def list_dynamic_connectors(self, workspace_id) -> list[dict[str, Any]]:
        rows = self.s.scalars(
            select(DynamicConnectorConfig).where(
                DynamicConnectorConfig.workspace_id == uuid.UUID(str(workspace_id))
            ).order_by(DynamicConnectorConfig.name)
        ).all()
        return [self._config_dict(r) for r in rows]

    def get_dynamic_connector(self, workspace_id, config_id: str) -> dict[str, Any]:
        return self._config_dict(self._get_dynamic_config(workspace_id, config_id))

    def create_dynamic_connector(
        self, workspace_id, user_id, fields: dict[str, Any]
    ) -> dict[str, Any]:
        row = DynamicConnectorConfig(
            workspace_id=uuid.UUID(str(workspace_id)),
            created_by=uuid.UUID(str(user_id)),
            name=fields.get("name", "Untitled"),
            base_url=fields.get("base_url", ""),
            auth_type=fields.get("auth_type", "none"),
            auth_config=fields.get("auth_config") or {},
            headers=fields.get("headers") or {},
            pagination=fields.get("pagination") or {},
            mappings=fields.get("mappings") or {},
            enabled=fields.get("enabled", True),
        )
        self.s.add(row)
        self.s.commit()
        return self._config_dict(row)

    def update_dynamic_connector(
        self, workspace_id, config_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        row = self._get_dynamic_config(workspace_id, config_id)
        for key in (
            "name",
            "base_url",
            "auth_type",
            "auth_config",
            "headers",
            "pagination",
            "mappings",
            "enabled",
        ):
            if key in fields:
                setattr(row, key, fields[key])
        self.s.commit()
        return self._config_dict(row)

    def delete_dynamic_connector(self, workspace_id, config_id: str) -> dict[str, Any]:
        row = self._get_dynamic_config(workspace_id, config_id)
        self.s.delete(row)
        self.s.commit()
        return {"deleted": True}

    def test_dynamic_connector(
        self, workspace_id, config_id: str
    ) -> dict[str, Any]:
        row = self._get_dynamic_config(workspace_id, config_id)
        connector = DynamicRestConnector()
        start = datetime.now(UTC)
        try:
            with connector._client(row) as client:  # noqa: SLF001
                resp = client.get("/")
                resp.raise_for_status()
                body = resp.text[:500]
                status = "ok"
                http_status = resp.status_code
        except Exception as exc:
            status = "error"
            body = str(exc)[:500]
            http_status = getattr(getattr(exc, "response", None), "status_code", None)
        elapsed_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
        row.last_tested_at = datetime.now(UTC)
        row.last_test_status = status
        self.s.commit()
        return {
            "status": status,
            "http_status": http_status,
            "latency_ms": elapsed_ms,
            "preview": body,
            "config_id": config_id,
        }

    def poll_dynamic_connector(
        self, workspace_id, config_id: str, user_id
    ) -> dict[str, Any]:
        row = self._get_dynamic_config(workspace_id, config_id)
        # Find or create an IntegrationSource bound to this dynamic config.
        source = self.s.scalar(
            select(IntegrationSource).where(
                IntegrationSource.workspace_id == uuid.UUID(str(workspace_id)),
                IntegrationSource.adapter_kind == "dynamic",
                IntegrationSource.name == f"dynamic:{row.id}",
            )
        )
        if source is None:
            source = IntegrationSource(
                workspace_id=uuid.UUID(str(workspace_id)),
                created_by=uuid.UUID(str(user_id)),
                adapter_kind="dynamic",
                name=f"dynamic:{row.id}",
                config={"dynamic_connector_id": str(row.id)},
                status="configured",
            )
            self.s.add(source)
            self.s.commit()
        return self.poll_source(workspace_id, str(source.id), user_id)
