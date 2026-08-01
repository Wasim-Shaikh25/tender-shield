"""Per-project subscription activation from verified webhooks (TS-256)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.billing.models import ProjectSubscription
from app.modules.billing.plans import PROJECT_ACTIVATION_PRICE_INR_PAISE


def validate_project_amount(currency: str, amount_minor: int) -> bool:
    return currency.upper() == "INR" and amount_minor == PROJECT_ACTIVATION_PRICE_INR_PAISE


def activate_from_webhook(
    session: Session,
    *,
    notes: dict,
    provider: str,
    provider_order_id: str,
    amount_minor: int,
    currency: str,
    publish=None,
) -> bool:
    opportunity_id = notes.get("opportunity_id")
    workspace_id = notes.get("workspace_id")
    if not opportunity_id or not workspace_id:
        return False
    if not validate_project_amount(currency, amount_minor):
        return False

    wid = uuid.UUID(str(workspace_id))
    oid = uuid.UUID(str(opportunity_id))
    row = session.scalar(
        select(ProjectSubscription).where(
            ProjectSubscription.workspace_id == wid,
            ProjectSubscription.opportunity_id == oid,
        )
    )
    if row is None:
        row = ProjectSubscription(
            workspace_id=wid,
            opportunity_id=oid,
            status="pending",
            activation_fee_minor=amount_minor,
            currency=currency.upper(),
            provider=provider,
            provider_order_id=provider_order_id,
        )
        session.add(row)
    if row.status == "active" and row.activated_at is not None:
        return True

    row.status = "active"
    row.activated_at = datetime.now(UTC)
    row.provider = provider
    row.provider_order_id = provider_order_id
    session.commit()
    if publish:
        publish(
            "billing.project_activated",
            {
                "workspace_id": str(wid),
                "opportunity_id": str(oid),
                "provider": provider,
            },
        )
    return True


def is_project_active(session: Session, workspace_id, opportunity_id) -> bool:
    row = session.scalar(
        select(ProjectSubscription).where(
            ProjectSubscription.workspace_id == uuid.UUID(str(workspace_id)),
            ProjectSubscription.opportunity_id == uuid.UUID(str(opportunity_id)),
            ProjectSubscription.status == "active",
        )
    )
    return row is not None and row.activated_at is not None
