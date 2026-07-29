"""ComparisonService — portfolio-level ranking of opportunities.

Consumes ingestion, findings, and drafting via the registry. No direct imports
of other modules' models.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session


class ComparisonService:
    def __init__(
        self,
        session: Session,
        *,
        ingestion_factory: Callable[[Session], object] | None = None,
        findings_factory: Callable[[Session], object] | None = None,
        drafting_factory: Callable[[Session], object] | None = None,
    ):
        self.s = session
        self._ingestion_factory = ingestion_factory
        self._findings_factory = findings_factory
        self._drafting_factory = drafting_factory

    def compare(self, workspace_id) -> list[dict]:
        opps = self._opportunities(workspace_id)
        rows = []
        for opp in opps:
            opp_id = str(opp.id)
            metrics = self._metrics_for(workspace_id, opp_id)
            rows.append(
                {
                    "id": opp_id,
                    "title": getattr(opp, "title", ""),
                    "submission_due": metrics["submission_due"],
                    "days_to_submission": metrics["days_to_submission"],
                    "risk": metrics["risk"],
                    "qualification_gaps": metrics["qualification_gaps"],
                    "boq_defects": metrics["boq_defects"],
                    "standard_violations": metrics["standard_violations"],
                    "bid_readiness_score": metrics["bid_readiness_score"],
                    "recommendation": metrics["recommendation"],
                }
            )

        # Stable deterministic ranking.
        for idx, row in enumerate(_rank(rows), start=1):
            row["priority_score"] = _priority_score(row)
            row["rank"] = idx
        return rows

    def _opportunities(self, workspace_id) -> list:
        if self._ingestion_factory is None:
            return []
        svc = self._ingestion_factory(self.s)
        if not hasattr(svc, "list_opportunities"):
            return []
        return svc.list_opportunities(workspace_id)

    def _metrics_for(self, workspace_id, opportunity_id: str) -> dict:
        submission_due = self._submission_due(workspace_id, opportunity_id)
        days_to_submission = None
        if submission_due:
            ref = datetime.now(UTC) if submission_due.tzinfo else datetime.now()
            delta = submission_due - ref
            days_to_submission = max(0, delta.days)

        risk = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        qualification_gaps = 0
        boq_defects = 0
        standard_violations = 0

        findings = self._findings(workspace_id, opportunity_id)
        for f in findings:
            kind = getattr(f, "kind", "") or ""
            severity = getattr(f, "severity", "") or ""
            if kind == "risk_clause" or kind.startswith("risk"):
                if severity in risk:
                    risk[severity] += 1
                else:
                    risk["info"] += 1
            elif kind == "qualification_gap":
                qualification_gaps += 1
            elif kind == "boq_defect":
                boq_defects += 1
            elif kind == "standard_violation":
                standard_violations += 1

        score, recommendation = self._bid_decision(workspace_id, opportunity_id)

        return {
            "submission_due": submission_due.isoformat() if submission_due else None,
            "days_to_submission": days_to_submission,
            "risk": risk,
            "qualification_gaps": qualification_gaps,
            "boq_defects": boq_defects,
            "standard_violations": standard_violations,
            "bid_readiness_score": score,
            "recommendation": recommendation,
        }

    def _submission_due(self, workspace_id, opportunity_id: str):
        if self._ingestion_factory is None:
            return None
        svc = self._ingestion_factory(self.s)
        # Prefer the explicit submission_due on the opportunity.
        if hasattr(svc, "get_opportunity"):
            opp = svc.get_opportunity(workspace_id, opportunity_id)
            if opp is not None and getattr(opp, "submission_due", None) is not None:
                return opp.submission_due
        # Fall back to the earliest bid_submission deadline.
        if hasattr(svc, "list_deadlines"):
            earliest = None
            for dl in svc.list_deadlines(workspace_id, opportunity_id):
                if getattr(dl, "kind", "") in {"bid_submission", "submission"}:
                    due = getattr(dl, "due_at", None)
                    if due is not None and (earliest is None or due < earliest):
                        earliest = due
            return earliest
        return None

    def _findings(self, workspace_id, opportunity_id: str) -> list:
        if self._findings_factory is None:
            return []
        svc = self._findings_factory(self.s)
        if not hasattr(svc, "list"):
            return []
        return svc.list(workspace_id, opportunity_id)

    def _bid_decision(self, workspace_id, opportunity_id: str) -> tuple:
        if self._drafting_factory is None:
            return None, None
        svc = self._drafting_factory(self.s)
        if not hasattr(svc, "list"):
            return None, None
        try:
            artifacts = svc.list(workspace_id, opportunity_id)
        except Exception:
            return None, None
        bid_artifacts = [a for a in artifacts if getattr(a, "kind", None) == "bid_decision"]
        if not bid_artifacts:
            return None, None
        latest = max(bid_artifacts, key=lambda a: getattr(a, "version", 0) or 0)
        body = getattr(latest, "body", {}) or {}
        score = body.get("score") if isinstance(body, dict) else None
        recommendation = body.get("recommendation") if isinstance(body, dict) else None
        return score, recommendation


def _priority_score(row: dict) -> float:
    """A stable numeric proxy for the sort order."""
    rec = row.get("recommendation")
    rec_rank = {"proceed": 3, "proceed_with_conditions": 2, "do_not_proceed": 1}.get(rec, 0)
    score = row.get("bid_readiness_score") or 0
    risk = row.get("risk", {})
    critical = risk.get("critical", 0)
    days = row.get("days_to_submission")
    days_value = 999 if days is None else days
    # High score, low critical risk, more time → higher priority.
    return (rec_rank * 1_000_000) + (score * 1_000) - (critical * 10_000) - days_value


def _rank(rows: list[dict]) -> list[dict]:
    def sort_key(row: dict):
        rec = row.get("recommendation")
        rec_rank = {"proceed": 0, "proceed_with_conditions": 1, "do_not_proceed": 2}.get(rec, 3)
        score = -(row.get("bid_readiness_score") or 0)
        critical = row.get("risk", {}).get("critical", 0)
        days = row.get("days_to_submission")
        days_value = 9999 if days is None else days
        return (rec_rank, score, critical, days_value, row.get("title", ""))

    return sorted(rows, key=sort_key)
