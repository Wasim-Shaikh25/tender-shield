"""DraftingService — generate bid-decision artifacts from ACCEPTED findings,
every one gated by the three validators (Doc §6.5). Consumes the findings store
via capability; never imports findings/review."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.drafting.generator import build_body, render_text
from app.modules.drafting.models import Artifact
from app.modules.drafting.validators import FactTable, validate

KINDS = {"clarification_letter", "assumptions_register"}
_ACCEPTED = {"accepted", "edited"}


class DraftingError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class DraftingService:
    def __init__(self, session: Session, *, store_factory=None):
        self.s = session
        self._store_factory = store_factory

    def _accepted_findings(self, org_id, opportunity_id) -> list[dict]:
        if self._store_factory is None:
            raise DraftingError("findings_unavailable")
        rows = self._store_factory(self.s).list(org_id, opportunity_id)
        return [
            {
                "title": r.title,
                "category": r.category,
                "detail": r.detail,
                "source_quote": r.source_quote,
                "source_page": r.source_page,
                "amount_exposure": (
                    float(r.amount_exposure) if r.amount_exposure is not None else None
                ),
                "suggested_action": r.suggested_action,
            }
            for r in rows
            if r.review_status in _ACCEPTED
        ]

    def generate(self, org_id, opportunity_id, kind: str, opportunity_title: str = "") -> Artifact:
        if kind not in KINDS:
            raise DraftingError("bad_kind")
        findings = self._accepted_findings(org_id, opportunity_id)
        if not findings:
            raise DraftingError("no_accepted_findings")

        body = build_body(kind, opportunity_title or "this tender", findings)
        # The spine: the assembled prose must contain no invented quote/clause/
        # number beyond the accepted-findings fact table (Doc §6.5).
        validate(render_text(body), FactTable.from_findings(findings))

        opp = uuid.UUID(str(opportunity_id))
        next_version = (
            self.s.scalar(
                select(func.coalesce(func.max(Artifact.version), 0)).where(
                    Artifact.opportunity_id == opp, Artifact.kind == kind
                )
            )
            + 1
        )
        artifact = Artifact(
            org_id=uuid.UUID(str(org_id)),
            opportunity_id=opp,
            kind=kind,
            version=next_version,
            body=body,
            model_meta={"generator": "deterministic", "findings": len(findings)},
        )
        self.s.add(artifact)
        self.s.commit()
        return artifact

    def list(self, org_id, opportunity_id) -> list[Artifact]:
        return list(
            self.s.scalars(
                select(Artifact)
                .where(
                    Artifact.org_id == uuid.UUID(str(org_id)),
                    Artifact.opportunity_id == uuid.UUID(str(opportunity_id)),
                )
                .order_by(Artifact.kind, Artifact.version.desc())
            )
        )

    def get(self, org_id, artifact_id) -> Artifact | None:
        return self.s.scalar(
            select(Artifact).where(
                Artifact.id == uuid.UUID(str(artifact_id)),
                Artifact.org_id == uuid.UUID(str(org_id)),
            )
        )
