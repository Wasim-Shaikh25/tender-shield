"""Advisor Edition service (TS-290, TS-291)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.advisor.models import AdvisorClient, AdvisorReviewQueueItem, AdvisorTemplate


class AdvisorError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class AdvisorService:
    def __init__(
        self,
        session: Session,
        *,
        billing_factory: Callable[[Session], object] | None = None,
        publish: Callable[[str, dict], Any] | None = None,
    ) -> None:
        self.s = session
        self._billing_factory = billing_factory
        self._publish = publish or (lambda event, payload: None)

    def create_client(
        self,
        workspace_id,
        *,
        client_workspace_id,
        name: str,
        billing_rate: str | None = None,
    ) -> AdvisorClient:
        row = AdvisorClient(
            workspace_id=uuid.UUID(str(workspace_id)),
            client_workspace_id=uuid.UUID(str(client_workspace_id)),
            name=name,
            billing_rate=billing_rate,
        )
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        self._publish(
            "advisor.client_linked",
            {
                "workspace_id": str(workspace_id),
                "client_workspace_id": str(client_workspace_id),
                "advisor_client_id": str(row.id),
            },
        )
        return row

    def list_clients(self, workspace_id) -> list[AdvisorClient]:
        return list(
            self.s.scalars(
                select(AdvisorClient).where(
                    AdvisorClient.workspace_id == uuid.UUID(str(workspace_id)),
                    AdvisorClient.status == "active",
                )
            )
        )

    def client_usage(self, workspace_id, client_id) -> dict:
        client = self.s.scalar(
            select(AdvisorClient).where(
                AdvisorClient.id == uuid.UUID(str(client_id)),
                AdvisorClient.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )
        if client is None:
            raise AdvisorError("not_found")

        # Derive a simple usage summary from known counts in this module.
        # A future integration with the billing module will enrich this.
        review_count = self.s.scalar(
            select(func.count(AdvisorReviewQueueItem.id)).where(
                AdvisorReviewQueueItem.workspace_id == uuid.UUID(str(workspace_id)),
                AdvisorReviewQueueItem.client_workspace_id == client.client_workspace_id,
            )
        )

        return {
            "client_id": str(client.id),
            "client_workspace_id": str(client.client_workspace_id),
            "period": datetime.now(UTC).strftime("%Y-%m"),
            "review_items": review_count or 0,
        }

    def create_review_item(
        self,
        workspace_id,
        *,
        client_workspace_id,
        opportunity_id,
        title: str,
        assigned_to: str | None = None,
        priority: int = 0,
        status: str = "pending",
        due_date: date | None = None,
    ) -> AdvisorReviewQueueItem:
        row = AdvisorReviewQueueItem(
            workspace_id=uuid.UUID(str(workspace_id)),
            client_workspace_id=uuid.UUID(str(client_workspace_id)),
            opportunity_id=uuid.UUID(str(opportunity_id)),
            title=title,
            assigned_to=uuid.UUID(str(assigned_to)) if assigned_to else None,
            priority=priority,
            status=status,
            due_date=due_date,
        )
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        self._publish(
            "advisor.review_queued",
            {
                "workspace_id": str(workspace_id),
                "item_id": str(row.id),
                "client_workspace_id": str(client_workspace_id),
            },
        )
        return row

    def list_review_items(
        self, workspace_id, *, status: str | None = None
    ) -> list[AdvisorReviewQueueItem]:
        stmt = select(AdvisorReviewQueueItem).where(
            AdvisorReviewQueueItem.workspace_id == uuid.UUID(str(workspace_id))
        )
        if status:
            stmt = stmt.where(AdvisorReviewQueueItem.status == status)
        return list(self.s.scalars(stmt.order_by(AdvisorReviewQueueItem.priority.desc())))

    def update_review_item_status(
        self, workspace_id, item_id, status: str
    ) -> AdvisorReviewQueueItem:
        row = self.s.scalar(
            select(AdvisorReviewQueueItem).where(
                AdvisorReviewQueueItem.id == uuid.UUID(str(item_id)),
                AdvisorReviewQueueItem.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )
        if row is None:
            raise AdvisorError("not_found")
        row.status = status
        self.s.commit()
        self.s.refresh(row)
        return row

    def create_template(
        self,
        workspace_id,
        *,
        name: str,
        client_workspace_id: str | None = None,
        theme: dict | None = None,
        header_text: str | None = None,
        footer_text: str | None = None,
    ) -> AdvisorTemplate:
        row = AdvisorTemplate(
            workspace_id=uuid.UUID(str(workspace_id)),
            name=name,
            client_workspace_id=(
                uuid.UUID(str(client_workspace_id)) if client_workspace_id else None
            ),
            theme=theme or {},
            header_text=header_text,
            footer_text=footer_text,
        )
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        return row

    def list_templates(self, workspace_id) -> list[AdvisorTemplate]:
        return list(
            self.s.scalars(
                select(AdvisorTemplate).where(
                    AdvisorTemplate.workspace_id == uuid.UUID(str(workspace_id))
                )
            )
        )

    def template_config(self, workspace_id, template_id) -> dict:
        row = self.s.scalar(
            select(AdvisorTemplate).where(
                AdvisorTemplate.id == uuid.UUID(str(template_id)),
                AdvisorTemplate.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )
        if row is None:
            raise AdvisorError("not_found")
        return {
            "template_id": str(row.id),
            "name": row.name,
            "theme": row.theme or {},
            "header_text": row.header_text,
            "footer_text": row.footer_text,
        }
