"""WorkspaceAdmin — read/update the billing-relevant columns on the workspaces table.

Published as the `auth.workspace_factory` capability so billing (and admin) can
manage plan state without importing auth's models."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import Workspace


class WorkspaceAdminError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


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

    def get_or_create_referral_code(self, workspace_id) -> str:
        """Generated lazily on first request rather than at signup — most
        workspaces will never look at `GET /billing/referral` (R-006 §B.7),
        so there is no reason to burn a code (and the uniqueness-retry loop
        below) on every signup."""
        workspace = self.get(workspace_id)
        if workspace is None:
            raise WorkspaceAdminError("no_workspace")
        if workspace.referral_code:
            return workspace.referral_code
        for _ in range(5):  # collision is astronomically unlikely; bounded retry, not forever
            code = secrets.token_hex(4).upper()
            if not self.s.scalar(select(Workspace).where(Workspace.referral_code == code)):
                workspace.referral_code = code
                self.s.commit()
                return code
        raise WorkspaceAdminError("referral_code_generation_failed")

    def owner_email_domain(self, workspace_id) -> str | None:
        """Snapshotted into billing's `referral_codes` pointer table when a
        code is generated (R-006 §B.7/A9), so the self-referral domain check
        never needs a second cross-tenant lookup at redemption time. Only
        safe to call here for the CALLER'S OWN workspace_id — `self.get()`
        reads the RLS-protected `workspaces` table, so a different
        workspace_id than the one currently bound would silently return None
        under RLS, the same trap `find_by_referral_code` fell into (removed;
        see billing's `referral_codes` table and its migration note)."""
        from app.modules.auth.models import User

        workspace = self.get(workspace_id)
        if workspace is None:
            return None
        owner = self.s.get(User, workspace.owner_id)
        if owner is None or "@" not in owner.email:
            return None
        return owner.email.rsplit("@", 1)[1].lower()

    def start_trial(self, workspace_id, *, days: int) -> datetime:
        """A workspace may hold one trial, ever (R-006 §B.8) — `had_trial`
        is set the moment a trial starts, not when it ends, so it can never
        be restarted by any path (including a later downgrade back to
        free)."""
        workspace = self.get(workspace_id)
        if workspace is None:
            raise WorkspaceAdminError("no_workspace")
        if workspace.had_trial:
            raise WorkspaceAdminError("trial_already_used")
        ends_at = datetime.now(UTC) + timedelta(days=days)
        workspace.trial_ends_at = ends_at
        workspace.had_trial = True
        self.s.commit()
        return ends_at

    def set_comp(self, workspace_id, *, plan: str, expires_at: datetime | None) -> None:
        """Superadmin pilot/goodwill grant (R-006 §B.9) — a paid plan with no
        real payment behind it, auto-reverting once `expires_at` passes
        (`BillingService._effective_plan_and_status` checks this lazily; no
        scheduled job needed). `billing_provider="comp"` marks the workspace
        so a future revenue-metrics system can exclude it (R-006 §B.11) —
        no such system exists yet to actually do the excluding."""
        workspace = self.get(workspace_id)
        if workspace is None:
            raise WorkspaceAdminError("no_workspace")
        workspace.plan = plan
        workspace.billing_provider = "comp"
        workspace.comp_expires_at = expires_at
        self.s.commit()
