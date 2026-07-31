"""Express purchase activation from verified billing webhooks (TS-212)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.express.models import ExPurchase, ExSession
from app.modules.express.prices import validate_express_amount


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
    """Activate an express purchase after billing webhook verification."""
    express_session_id = notes.get("express_session_id")
    token = notes.get("express_token")
    tier = notes.get("tier", "snapshot")
    if not validate_express_amount(tier, currency, amount_minor):
        return False

    row = None
    if express_session_id:
        row = session.scalar(
            select(ExSession).where(ExSession.id == uuid.UUID(str(express_session_id)))
        )
    if row is None and token:
        row = session.scalar(select(ExSession).where(ExSession.token == token))
    if row is None:
        return False

    purchase = session.scalar(
        select(ExPurchase).where(
            ExPurchase.session_id == row.id,
            ExPurchase.provider == provider,
            ExPurchase.provider_order_id == provider_order_id,
        )
    )
    if purchase is None:
        purchase = ExPurchase(
            workspace_id=row.workspace_id,
            session_id=row.id,
            provider=provider,
            provider_order_id=provider_order_id,
            amount_minor=amount_minor,
            currency=currency.upper(),
        )
        session.add(purchase)
    if purchase.activated_at is not None:
        return True

    purchase.activated_at = datetime.now(UTC)
    row.state = "purchased"
    session.commit()
    if publish:
        publish(
            "express.purchased",
            {
                "token": row.token,
                "session_id": str(row.id),
                "workspace_id": str(row.workspace_id),
                "provider": provider,
            },
        )
    return True
