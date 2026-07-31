"""Correction loop service (TS-218)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.rulepacks.corrections import aggregate_pattern_stats, suggest_overlay
from app.modules.rulepacks.models import CorrectionProposal


class CorrectionError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class CorrectionService:
    def __init__(
        self,
        session: Session,
        *,
        findings_factory: Callable | None = None,
        ingestion_factory: Callable | None = None,
        publish: Callable[[str, dict], int] | None = None,
        pack_id: str = "in-works",
    ):
        self.s = session
        self._findings_factory = findings_factory
        self._ingestion_factory = ingestion_factory
        self._publish = publish
        self._pack_id = pack_id

    def _family_map(self, workspace_id) -> dict[str, str | None]:
        if self._ingestion_factory is None:
            return {}
        ing = self._ingestion_factory(self.s)
        if not hasattr(ing, "list_opportunities"):
            return {}
        return {
            str(opp.id): getattr(opp, "employer_family", None)
            for opp in ing.list_opportunities(workspace_id)
        }

    def scan(self, workspace_id) -> dict:
        if self._findings_factory is None:
            raise CorrectionError("findings_unavailable")
        store = self._findings_factory(self.s)
        if not hasattr(store, "list_for_workspace"):
            raise CorrectionError("findings_unavailable")

        findings = store.list_for_workspace(workspace_id)
        stats_rows = aggregate_pattern_stats(
            findings,
            family_for_opportunity=self._family_map(workspace_id),
        )
        created = 0
        for stats in stats_rows:
            overlay = suggest_overlay(stats)
            if overlay is None:
                continue
            existing = self.s.scalar(
                select(CorrectionProposal).where(
                    CorrectionProposal.workspace_id == uuid.UUID(str(workspace_id)),
                    CorrectionProposal.pack_id == self._pack_id,
                    CorrectionProposal.pattern_id == stats.pattern_id,
                    CorrectionProposal.employer_family == stats.employer_family,
                    CorrectionProposal.status == "proposed",
                )
            )
            if existing is not None:
                existing.stats = {
                    "reviewed": stats.reviewed,
                    "false_positive_rate": stats.false_positive_rate,
                    "accepted": stats.accepted,
                    "rejected": stats.rejected,
                    "false_positive": stats.false_positive,
                }
                existing.overlay = overlay
                continue
            row = CorrectionProposal(
                workspace_id=uuid.UUID(str(workspace_id)),
                pack_id=self._pack_id,
                pattern_id=stats.pattern_id,
                employer_family=stats.employer_family,
                status="proposed",
                overlay=overlay,
                stats={
                    "reviewed": stats.reviewed,
                    "false_positive_rate": stats.false_positive_rate,
                    "accepted": stats.accepted,
                    "rejected": stats.rejected,
                    "false_positive": stats.false_positive,
                },
            )
            self.s.add(row)
            created += 1
            if self._publish:
                self._publish(
                    "pattern.correction_suggested",
                    {
                        "workspace_id": str(workspace_id),
                        "pattern_id": stats.pattern_id,
                        "employer_family": stats.employer_family,
                    },
                )
        self.s.commit()
        return {"scanned": len(stats_rows), "proposals_created": created}

    def list_proposals(self, workspace_id, *, status: str | None = None) -> list[dict]:
        stmt = select(CorrectionProposal).where(
            CorrectionProposal.workspace_id == uuid.UUID(str(workspace_id))
        )
        if status:
            stmt = stmt.where(CorrectionProposal.status == status)
        rows = self.s.scalars(stmt.order_by(CorrectionProposal.created_at.desc()))
        return [
            {
                "id": str(row.id),
                "pack_id": row.pack_id,
                "pattern_id": row.pattern_id,
                "employer_family": row.employer_family,
                "status": row.status,
                "overlay": row.overlay,
                "stats": row.stats,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
            }
            for row in rows
        ]

    def dismiss(self, workspace_id, proposal_id, *, reviewer_id) -> dict:
        row = self._get(workspace_id, proposal_id)
        if row.status != "proposed":
            raise CorrectionError("already_reviewed")
        row.status = "dismissed"
        row.reviewed_at = datetime.now(UTC)
        row.reviewed_by = uuid.UUID(str(reviewer_id))
        self.s.commit()
        return {"id": str(row.id), "status": row.status}

    def _get(self, workspace_id, proposal_id) -> CorrectionProposal:
        row = self.s.scalar(
            select(CorrectionProposal).where(
                CorrectionProposal.id == uuid.UUID(str(proposal_id)),
                CorrectionProposal.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )
        if row is None:
            raise CorrectionError("not_found")
        return row
