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

    def get(self, org_id, finding_id) -> FindingRow | None:
        return self.s.scalar(
            select(FindingRow).where(
                FindingRow.id == uuid.UUID(str(finding_id)),
                FindingRow.org_id == uuid.UUID(str(org_id)),
            )
        )

    def set_review(
        self,
        org_id,
        finding_id,
        *,
        status,
        note=None,
        review_reason=None,
        reviewer_id=None,
    ) -> FindingRow | None:
        """Set the review columns on a finding (called by the review module via
        the store capability — the findings module owns these columns)."""
        row = self.get(org_id, finding_id)
        if row is None:
            return None
        row.review_status = status
        row.review_note = note
        row.review_reason = review_reason
        row.reviewed_by = uuid.UUID(str(reviewer_id)) if reviewer_id else None
        self.s.commit()
        return row

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
            review_reason=f.review_reason,
            explanation=f.explanation,
        )
