"""OrgAdmin — read/update the billing-relevant columns on the orgs table.

Published as the `auth.orgs_factory` capability so billing (and admin) can
manage plan state without importing auth's models."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import Org


class OrgAdmin:
    def __init__(self, session: Session):
        self.s = session

    def get(self, org_id) -> Org | None:
        return self.s.scalar(select(Org).where(Org.id == uuid.UUID(str(org_id))))

    def mark_free_review_used(self, org_id) -> None:
        org = self.get(org_id)
        if org:
            org.free_review_used = True
            self.s.commit()

    def set_plan(self, org_id, plan: str) -> None:
        org = self.get(org_id)
        if org:
            org.plan = plan
            self.s.commit()
