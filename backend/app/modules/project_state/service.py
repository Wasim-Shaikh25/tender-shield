"""ProjectStateService — compute deterministic project state and next actions.

The state is derived from ingestion, findings, and baseline modules through registry
capabilities so this module does not import their internals.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

_RESOLVED_STATUSES = {"accepted", "edited", "rejected", "false_positive"}

_STATE_ORDER = [
    "draft",
    "ingesting",
    "ingested",
    "reviewing",
    "reviewed",
    "baseline_locked",
    "submitted",
    "awarded",
    "rejected",
    "withdrawn",
]

_STATE_LABELS = {
    "draft": "Draft",
    "ingesting": "Ingesting",
    "ingested": "Ingested",
    "reviewing": "Reviewing",
    "reviewed": "Reviewed",
    "baseline_locked": "Baseline locked",
    "submitted": "Submitted",
    "awarded": "Awarded",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn",
}

_NEXT_ACTIONS = {
    "draft": {
        "label": "Upload tender documents",
        "link": "/opportunities/{id}?tab=documents",
    },
    "ingesting": {
        "label": "Wait for document processing",
        "link": "/opportunities/{id}",
    },
    "ingested": {
        "label": "Run risk and BOQ analysis",
        "link": "/opportunities/{id}?tab=risk",
    },
    "reviewing": {
        "label": "Review risk and BOQ findings",
        "link": "/opportunities/{id}?tab=findings",
    },
    "reviewed": {
        "label": "Lock commercial baseline",
        "link": "/opportunities/{id}?tab=baseline",
    },
    "baseline_locked": {
        "label": "Prepare bid submission",
        "link": "/opportunities/{id}?tab=export",
    },
    "submitted": {
        "label": "Track award outcome",
        "link": "/opportunities/{id}?tab=outcome",
    },
    "awarded": {
        "label": "Manage subcontracts and changes",
        "link": "/opportunities/{id}?tab=subcontracts",
    },
    "rejected": {
        "label": "Archive project",
        "link": "/opportunities/{id}",
    },
    "withdrawn": {
        "label": "Project withdrawn",
        "link": "/opportunities/{id}",
    },
}


def _now() -> datetime:
    return datetime.now(UTC)


def _days_until(deadline: datetime | None, now: datetime) -> int | None:
    if deadline is None:
        return None
    delta = deadline - now
    return max(delta.days, 0)


class ProjectStateService:
    def __init__(
        self,
        session: Session,
        *,
        workspace_factory,
        ingestion_factory,
        findings_factory,
        baseline_factory=None,
    ):
        self.s = session
        self._workspace_factory = workspace_factory
        self._ingestion_factory = ingestion_factory
        self._findings_factory = findings_factory
        self._baseline_factory = baseline_factory

    # ---- workspace membership ------------------------------------------------

    def allowed_workspace_ids(self, user_id) -> set[uuid.UUID]:
        """Return the workspace IDs the user is a member of."""
        ws = self._workspace_factory(self.s)
        rows = ws.list_for_user(user_id)
        return {uuid.UUID(str(r["workspace_id"])) for r in rows}

    # ---- state computation ---------------------------------------------------

    def state_for_opportunity(self, workspace_id, opportunity_id) -> dict:
        """Compute a full state card for a single opportunity."""
        ingestion = self._ingestion_factory(self.s)
        findings_store = self._findings_factory(self.s)

        opp = ingestion.get_opportunity(workspace_id, opportunity_id)
        if opp is None:
            raise ValueError("not_found")

        documents = ingestion.list_documents(workspace_id, opportunity_id, limit=None)
        findings = findings_store.list(workspace_id, opportunity_id)

        baselines = []
        if self._baseline_factory is not None:
            baselines = self._baseline_factory(self.s).list(workspace_id, opportunity_id)

        state, blockers = self._derive_state(opp, documents, findings, baselines)
        health = self._derive_health(opp, state, findings)
        completed = self._completed_gates(state, documents, findings, baselines)
        deadline = opp.submission_due
        days = _days_until(deadline, _now())

        next_action = _NEXT_ACTIONS.get(state, _NEXT_ACTIONS["draft"]).copy()
        next_action["link"] = next_action["link"].format(id=str(opp.id))

        return {
            "opportunity_id": str(opp.id),
            "workspace_id": str(opp.workspace_id),
            "title": opp.title,
            "employer": opp.employer,
            "jurisdiction": opp.jurisdiction,
            "contract_value_minor": opp.contract_value_minor,
            "currency": opp.currency,
            "submission_due": deadline.isoformat() if deadline else None,
            "days_to_deadline": days,
            "state": state,
            "state_label": _STATE_LABELS.get(state, state),
            "health": health,
            "next_action": next_action,
            "blockers": blockers,
            "completed_gates": completed,
            "document_count": len(documents),
            "finding_count": len(findings),
            "unreviewed_finding_count": sum(
                1 for f in findings if f.review_status not in _RESOLVED_STATUSES
            ),
            "baseline_count": len(baselines),
        }

    def _derive_state(self, opp, documents, findings, baselines) -> tuple[str, list[dict]]:
        blockers: list[dict] = []

        # Manual final statuses win.
        if opp.status in ("awarded", "rejected", "withdrawn", "submitted"):
            return str(opp.status), blockers

        # Award baseline or award document means awarded.
        if baselines and any(getattr(b, "source", None) == "award" for b in baselines):
            return "awarded", blockers

        if baselines:
            return "baseline_locked", blockers

        unreviewed = [f for f in findings if f.review_status not in _RESOLVED_STATUSES]
        if findings:
            if unreviewed:
                blockers.append(
                    {
                        "kind": "unreviewed_findings",
                        "count": len(unreviewed),
                        "message": f"{len(unreviewed)} finding(s) need review",
                    }
                )
                return "reviewing", blockers
            return "reviewed", blockers

        if documents:
            pending = [d for d in documents if getattr(d, "ocr_status", "done") == "pending"]
            if pending:
                blockers.append(
                    {
                        "kind": "processing",
                        "count": len(pending),
                        "message": f"{len(pending)} document(s) still processing",
                    }
                )
                return "ingesting", blockers
            return "ingested", blockers

        blockers.append({"kind": "no_documents", "message": "No tender documents uploaded"})
        return "draft", blockers

    def _completed_gates(self, state, documents, findings, baselines) -> list[str]:
        completed: list[str] = []
        if documents:
            completed.append("documents_uploaded")
        if findings:
            completed.append("findings_generated")
        if all(f.review_status in _RESOLVED_STATUSES for f in findings):
            completed.append("findings_reviewed")
        if baselines:
            completed.append("baseline_locked")
        return completed

    def _derive_health(self, opp, state: str, findings) -> str:
        now = _now()
        deadline = opp.submission_due

        if state in ("awarded", "rejected", "withdrawn"):
            return "completed"

        unreviewed_critical = sum(
            1
            for f in findings
            if f.review_status not in _RESOLVED_STATUSES
            and f.severity == "critical"
        )
        unreviewed_high = sum(
            1
            for f in findings
            if f.review_status not in _RESOLVED_STATUSES
            and f.severity == "high"
        )
        if unreviewed_critical:
            return "poor"

        unreviewed_any = sum(
            1 for f in findings if f.review_status not in _RESOLVED_STATUSES
        )
        if state in ("draft", "ingesting") and deadline is not None and deadline < now:
            return "poor"
        if deadline is not None and deadline - now <= timedelta(days=7) and state not in (
            "baseline_locked",
            "submitted",
            "awarded",
            "rejected",
            "withdrawn",
        ):
            return "at_risk"
        if unreviewed_high or state == "reviewing" or unreviewed_any:
            return "at_risk"
        return "healthy"

    # ---- list / filter -------------------------------------------------------

    def list_opportunities(self, user_id, **filters) -> list[dict]:
        allowed = self.allowed_workspace_ids(user_id)
        workspace_filter = filters.get("workspace_id")
        if workspace_filter:
            ws_uuid = uuid.UUID(str(workspace_filter))
            if ws_uuid not in allowed:
                return []
            allowed = {ws_uuid}

        ingestion = self._ingestion_factory(self.s)
        rows: list[dict] = []
        for ws_id in allowed:
            for opp in ingestion.list_opportunities(ws_id):
                rows.append(self.state_for_opportunity(ws_id, opp.id))

        return self._apply_filters(rows, filters)

    def _apply_filters(self, rows: list[dict], filters: dict) -> list[dict]:
        status = filters.get("status")
        health = filters.get("health")
        jurisdiction = filters.get("jurisdiction")
        min_value = filters.get("min_value")
        max_value = filters.get("max_value")
        deadline_after = filters.get("deadline_after")
        deadline_before = filters.get("deadline_before")

        if status:
            rows = [r for r in rows if r["state"] == status]
        if health:
            rows = [r for r in rows if r["health"] == health]
        if jurisdiction:
            rows = [r for r in rows if r["jurisdiction"] == jurisdiction]
        if min_value is not None:
            rows = [r for r in rows if (r["contract_value_minor"] or 0) >= int(min_value)]
        if max_value is not None:
            rows = [r for r in rows if (r["contract_value_minor"] or 0) <= int(max_value)]
        if deadline_after:
            try:
                after = datetime.fromisoformat(deadline_after)
                rows = [
                    r
                    for r in rows
                    if r["submission_due"] is not None
                    and datetime.fromisoformat(r["submission_due"]) >= after
                ]
            except ValueError:
                pass
        if deadline_before:
            try:
                before = datetime.fromisoformat(deadline_before)
                rows = [
                    r
                    for r in rows
                    if r["submission_due"] is not None
                    and datetime.fromisoformat(r["submission_due"]) <= before
                ]
            except ValueError:
                pass

        return rows

    # ---- workspace summary ---------------------------------------------------

    def workspace_summaries(self, user_id) -> list[dict]:
        """Return state counts and upcoming deadlines per workspace."""
        allowed = self.allowed_workspace_ids(user_id)
        ingestion = self._ingestion_factory(self.s)

        summaries: list[dict] = []
        for ws_id in allowed:
            opps = ingestion.list_opportunities(ws_id)
            states: list[dict] = [
                self.state_for_opportunity(ws_id, opp.id) for opp in opps
            ]
            counts: dict[str, int] = {s: 0 for s in _STATE_ORDER}
            for s in states:
                counts[s["state"]] = counts.get(s["state"], 0) + 1
            upcoming = [
                {
                    "opportunity_id": s["opportunity_id"],
                    "title": s["title"],
                    "submission_due": s["submission_due"],
                    "days_to_deadline": s["days_to_deadline"],
                    "state": s["state"],
                }
                for s in states
                if s["submission_due"]
                and s["days_to_deadline"] is not None
                and s["days_to_deadline"] <= 7
                and s["state"] not in ("awarded", "rejected", "withdrawn")
            ]
            upcoming.sort(key=lambda x: x["days_to_deadline"] or 0)

            ws = self._workspace_factory(self.s).get(ws_id)
            summaries.append(
                {
                    "workspace_id": str(ws_id),
                    "workspace_name": ws.name if ws else None,
                    "opportunity_count": len(states),
                    "state_counts": counts,
                    "upcoming_deadlines": upcoming[:5],
                }
            )
        return summaries
