"""ComparisonService — portfolio-level ranking of opportunities.

Consumes ingestion, findings, and drafting via the registry. No direct imports
of other modules' models.
"""

from __future__ import annotations

import re
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
        standards_factory: Callable[[Session], object] | None = None,
    ):
        self.s = session
        self._ingestion_factory = ingestion_factory
        self._findings_factory = findings_factory
        self._drafting_factory = drafting_factory
        self._standards_factory = standards_factory

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
            # Treat naive datetimes as UTC so the calculation is deterministic and
            # never mixes in the server's local time.
            ref = datetime.now(UTC)
            due = (
                submission_due
                if submission_due.tzinfo
                else submission_due.replace(tzinfo=UTC)
            )
            delta = due - ref
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

    def deviation_report(self, workspace_id, opportunity_id: str) -> dict:
        """Score each clause against the workspace's commercial standard/playbook.

        Returns per-clause deviation scores and an overall opportunity score.
        A negative `deviation_score` means the clause is below a `lt`/`lte` threshold;
        positive means it exceeds a `gt`/`gte` threshold. The score is normalised by
        the policy threshold so clauses on different scales are comparable.
        """
        clauses = self._clauses(workspace_id, opportunity_id)
        standards = self._standards(workspace_id)
        if not standards:
            return {"clauses": [], "overall_deviation_score": 0.0, "policies_checked": 0}
        policies = standards.list_policies(workspace_id)
        if not policies:
            return {"clauses": [], "overall_deviation_score": 0.0, "policies_checked": 0}

        clause_rows = []
        overall = 0.0
        for clause in clauses:
            text = " ".join(
                filter(None, [getattr(clause, "heading", None), getattr(clause, "text", "")])
            ).lower()
            matched = 0
            deviation = 0.0
            matched_policies = []
            for policy in policies:
                keywords = [k.lower() for k in policy.get("applies_to", [])]
                if keywords and not any(kw in text for kw in keywords):
                    continue
                value = _extract_clause_value(clause, policy.get("unit"))
                if value is None:
                    continue
                matched += 1
                threshold = policy.get("threshold") or 0
                if _policy_violates(value, policy.get("operator"), threshold):
                    if threshold:
                        score = (value - threshold) / threshold
                    else:
                        score = value
                    deviation += score
                    matched_policies.append(
                        {
                            "policy_key": policy["key"],
                            "policy_label": policy["label"],
                            "operator": policy["operator"],
                            "threshold": threshold,
                            "value": value,
                            "deviation_score": score,
                        }
                    )
            row = {
                "clause_ref": getattr(clause, "clause_ref", None),
                "heading": getattr(clause, "heading", None),
                "deviation_score": round(deviation, 4),
                "policies_matched": matched,
                "violations": matched_policies,
            }
            clause_rows.append(row)
            overall += deviation

        return {
            "clauses": sorted(clause_rows, key=lambda c: c["deviation_score"], reverse=True),
            "overall_deviation_score": round(overall, 4),
            "policies_checked": len(policies),
        }

    def _clauses(self, workspace_id, opportunity_id: str) -> list:
        if self._ingestion_factory is None:
            return []
        svc = self._ingestion_factory(self.s)
        if not hasattr(svc, "list_clauses"):
            return []
        return svc.list_clauses(workspace_id, opportunity_id)

    def _standards(self, workspace_id):
        if self._standards_factory is None:
            return None
        return self._standards_factory(self.s)

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


_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_DAYS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*days?", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)


def _extract_clause_value(clause, unit: str | None) -> float | None:
    text = " ".join(
        filter(None, [getattr(clause, "heading", None), getattr(clause, "text", "")])
    )
    if unit == "percent":
        m = _PERCENT_RE.search(text)
    elif unit == "days":
        m = _DAYS_RE.search(text)
    elif unit == "amount":
        m = _AMOUNT_RE.search(text)
    else:
        m = re.search(r"(\d+(?:\.\d+)?)", text)
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _policy_violates(value: float, operator: str | None, threshold: float) -> bool:
    if operator == "gt":
        return value > threshold
    if operator == "gte":
        return value >= threshold
    if operator == "lt":
        return value < threshold
    if operator == "lte":
        return value <= threshold
    return False
