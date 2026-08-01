"""Baseline adoption counts for analytics (TS-242).

Read-only queries over baseline-owned tables only — weekly activity is resolved
via the review module's audit capability (no cross-module imports).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.baseline.models import Baseline


def sealed_opportunity_count(session: Session, workspace_id) -> int:
    """Distinct opportunities with at least one sealed baseline row."""
    wid = uuid.UUID(str(workspace_id))
    return (
        session.scalar(
            select(func.count(func.distinct(Baseline.opportunity_id))).where(
                Baseline.workspace_id == wid
            )
        )
        or 0
    )
