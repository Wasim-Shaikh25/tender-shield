"""FindingStore — persistence for the shared findings table. Producers hand it
core `Finding` contract objects; it owns the row mapping and idempotent re-runs."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.contracts.findings import Finding
from app.modules.findings.models import FindingRow


class FindingStore:
    def __init__(self, session: Session):
        self.s = session

    def replace_for_producer(
        self, org_id, opportunity_id, producer: str, findings: list[Finding]
    ) -> list[FindingRow]:
        """Replace this producer's findings for the opportunity (idempotent
        re-run): a risk re-run never disturbs BOQ rows, and vice versa."""
        org = uuid.UUID(str(org_id))
        opp = uuid.UUID(str(opportunity_id))
        self.s.execute(
            delete(FindingRow).where(
                FindingRow.org_id == org,
                FindingRow.opportunity_id == opp,
                FindingRow.producer == producer,
            )
        )
        rows = [self._to_row(org, opp, producer, f) for f in findings]
        self.s.add_all(rows)
        self.s.commit()
        return rows

    def list(self, org_id, opportunity_id, *, producer: str | None = None) -> list[FindingRow]:
        stmt = select(FindingRow).where(
            FindingRow.org_id == uuid.UUID(str(org_id)),
            FindingRow.opportunity_id == uuid.UUID(str(opportunity_id)),
        )
        if producer:
            stmt = stmt.where(FindingRow.producer == producer)
        return list(self.s.scalars(stmt))

    @staticmethod
    def _to_row(org: uuid.UUID, opp: uuid.UUID, producer: str, f: Finding) -> FindingRow:
        return FindingRow(
            org_id=org,
            opportunity_id=opp,
            producer=producer,
            kind=f.kind.value,
            category=f.category,
            severity=f.severity.value,
            title=f.title,
            detail=f.detail,
            source=f.source.value,
            source_page=f.source_page,
            source_quote=f.source_quote,
            affected_trades=list(f.affected_trades),
            suggested_action=f.suggested_action,
            pattern_id=f.pattern_id,
            pattern_version=f.pattern_version,
            amount_exposure=f.amount_exposure,
            review_status=f.review_status.value,
        )
