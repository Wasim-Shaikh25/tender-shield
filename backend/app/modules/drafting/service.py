"""DraftingService — generate bid-decision artifacts from ACCEPTED findings,
every one gated by the three validators (Doc §6.5). Consumes the findings store
via capability; never imports findings/review."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.modules.drafting.generator import build_body, render_text
from app.modules.drafting.models import Artifact
from app.modules.drafting.validators import FactTable, validate

KINDS = {"clarification_letter", "assumptions_register", "bid_decision"}
_ACCEPTED = {"accepted", "edited"}
_RESOLVED = {"accepted", "edited", "rejected", "false_positive"}

_DEFAULT_WEIGHTS = {
    "risk": {"critical": 25, "high": 15, "medium": 8, "low": 3, "info": 0},
    "qualification": {"not_met": 20, "unknown": 10, "met": 0},
    "boq": {"critical": 15, "high": 10, "medium": 5, "low": 2, "info": 0},
    "standard_violation": 15,
}


class DraftingError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class DraftingService:
    def __init__(
        self,
        session: Session,
        *,
        store_factory=None,
        loader=None,
        standards_factory=None,
    ):
        self.s = session
        self._store_factory = store_factory
        self._loader = loader
        self._standards_factory = standards_factory

    def _accepted_findings(self, workspace_id, opportunity_id) -> list[dict]:
        if self._store_factory is None:
            raise DraftingError("findings_unavailable")
        rows = self._store_factory(self.s).list(workspace_id, opportunity_id)
        return [
            {
                "kind": r.kind,
                "title": r.title,
                "category": r.category,
                "severity": r.severity,
                "detail": r.detail,
                "source_quote": r.source_quote,
                "source_page": r.source_page,
                "amount_exposure": r.amount_exposure,
                "suggested_action": r.suggested_action,
                "explanation": r.explanation or {},
            }
            for r in rows
            if r.review_status in _ACCEPTED
        ]

    def _weights(self, workspace_id):
        weights = dict(_DEFAULT_WEIGHTS)
        if self._loader is not None:
            try:
                pack = self._loader.get_pack("in-works")
                override = (
                    (pack.playbooks or {})
                    .get("default_contractor", {})
                    .get("bid_decision_weights", {})
                )
                weights.update(override)
            except Exception:
                pass
        return weights

    def _review_gate_open(self, workspace_id, opportunity_id) -> bool:
        if self._store_factory is None:
            return True
        rows = self._store_factory(self.s).list(workspace_id, opportunity_id)
        return all(r.review_status in _RESOLVED for r in rows)

    def _extra_violations(self, workspace_id, opportunity_id, findings: list[dict]) -> list[dict]:
        if self._standards_factory is None:
            return []
        svc = self._standards_factory(self.s)
        if not hasattr(svc, "check_violations"):
            return []
        violations = svc.check_violations(workspace_id, findings)
        return [
            {
                "kind": "standard_violation",
                "title": f"Company standard violated: {v['policy_label']}",
                "category": "standard_violation",
                "severity": "high",
                "detail": (
                    f"Extracted value {v['value']} {v['operator']} threshold "
                    f"{v['threshold']} for policy '{v['policy_label']}'."
                ),
                "source_quote": v["finding"].get("source_quote"),
                "source_page": v["finding"].get("source_page"),
                "suggested_action": f"Review against company policy {v['policy_key']}.",
            }
            for v in violations
        ]

    def generate(
        self, workspace_id, opportunity_id, kind: str, opportunity_title: str = ""
    ) -> Artifact:
        if kind not in KINDS:
            raise DraftingError("bad_kind")
        if kind == "bid_decision" and not self._review_gate_open(workspace_id, opportunity_id):
            raise DraftingError("review_pending")
        findings = self._accepted_findings(workspace_id, opportunity_id)
        if not findings:
            raise DraftingError("no_accepted_findings")

        if kind == "bid_decision":
            findings = findings + self._extra_violations(workspace_id, opportunity_id, findings)

        weights = self._weights(workspace_id) if kind == "bid_decision" else None
        body = build_body(kind, opportunity_title or "this tender", findings, weights=weights)
        # The spine: the assembled prose must contain no invented quote/clause/
        # number beyond the accepted-findings fact table (Doc §6.5).
        validate(render_text(body), FactTable.from_findings(findings))

        opp = uuid.UUID(str(opportunity_id))
        # Compute the next version atomically inside the insert so concurrent
        # artifact generations cannot race on the same (opportunity_id, kind) pair.
        next_version_expr = (
            select(func.coalesce(func.max(Artifact.version), 0) + 1)
            .where(Artifact.opportunity_id == opp, Artifact.kind == kind)
            .scalar_subquery()
        )
        stmt = (
            insert(Artifact)
            .values(
                workspace_id=uuid.UUID(str(workspace_id)),
                opportunity_id=opp,
                kind=kind,
                version=next_version_expr,
                body=body,
                model_meta={"generator": "deterministic", "findings": len(findings)},
            )
            .returning(Artifact)
        )
        artifact = self.s.scalars(stmt).one()
        self.s.commit()
        return artifact

    def list(self, workspace_id, opportunity_id) -> list[Artifact]:
        return list(
            self.s.scalars(
                select(Artifact)
                .where(
                    Artifact.workspace_id == uuid.UUID(str(workspace_id)),
                    Artifact.opportunity_id == uuid.UUID(str(opportunity_id)),
                )
                .order_by(Artifact.kind, Artifact.version.desc())
            )
        )

    def get(self, workspace_id, artifact_id) -> Artifact | None:
        return self.s.scalar(
            select(Artifact).where(
                Artifact.id == uuid.UUID(str(artifact_id)),
                Artifact.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )
