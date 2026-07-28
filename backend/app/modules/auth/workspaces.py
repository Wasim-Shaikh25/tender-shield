"""WorkspaceAdmin — read/update the billing-relevant columns on the workspaces table.

Published as the `auth.workspace_factory` capability so billing (and admin) can
manage plan state without importing auth's models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import Workspace


class WorkspaceAdmin:
    def __init__(self, session: Session):
        self.s = session

    def get(self, workspace_id) -> Workspace | None:
        return self.s.scalar(select(Workspace).where(Workspace.id == uuid.UUID(str(workspace_id))))

    def mark_free_review_used(self, workspace_id) -> None:
        """No commit here — the caller controls the transaction boundary.

        authorize_review (R-004 §A.4) wraps this write together with a
        per-workspace advisory lock and a usage-event write in ONE
        transaction; committing here would end that transaction (and release
        the lock) before the rest of the metering logic runs, defeating the
        race-safety the lock exists for.
        """
        workspace = self.get(workspace_id)
        if workspace:
            workspace.free_review_used = True

    def set_plan(self, workspace_id, plan: str) -> None:
        """No commit here — see mark_free_review_used."""
        workspace = self.get(workspace_id)
        if workspace:
            workspace.plan = plan

    def set_plan_status(
        self,
        workspace_id,
        status: str,
        *,
        grace_until: datetime | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        provider_subscription_id: str | None = None,
    ) -> None:
        """Billing lifecycle transitions (R-005 §C.4). No commit — see
        mark_free_review_used."""
        workspace = self.get(workspace_id)
        if not workspace:
            return
        workspace.plan_status = status
        workspace.grace_until = grace_until
        if period_start is not None:
            workspace.current_period_start = period_start
        if period_end is not None:
            workspace.current_period_end = period_end
        if provider_subscription_id is not None:
            workspace.provider_subscription_id = provider_subscription_id

    def set_billing_details(
        self,
        workspace_id,
        *,
        legal_name: str | None,
        gstin: str | None,
        billing_address: dict,
        place_of_supply: str | None,
    ) -> None:
        """GST buyer identity (R-007 §B.1). GSTIN format/checksum validation
        happens in the billing router BEFORE this is called — this module
        never imports billing's `gst.py` (CLAUDE.md §2), so it trusts its
        caller the same way it already trusts `set_plan`'s caller."""
        workspace = self.get(workspace_id)
        if not workspace:
            return
        workspace.legal_name = legal_name
        workspace.gstin = gstin
        workspace.billing_address = billing_address
        workspace.place_of_supply = place_of_supply
        self.s.commit()
