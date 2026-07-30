"""AnalyticsService — internal accuracy dashboard.

Read-only aggregator over the findings store. Precision/recall are explicitly
proxies where real golden labels are absent.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.analytics.export import PlanDashboardExporter
from app.modules.analytics.models import PlanSnapshot
from app.modules.analytics.plan_agent import PlanDashboardAgent

_STATUSES = {"proposed", "accepted", "edited", "rejected", "false_positive", "needs_clarification"}


class AnalyticsError(Exception):
    """Domain error surfaced by the analytics router as an HTTP exception."""


class AnalyticsService:
    def __init__(
        self,
        session: Session,
        *,
        findings_factory: Callable[[Session], object] | None = None,
        ingestion_factory: Callable[[Session], object] | None = None,
    ):
        self.s = session
        self._findings_factory = findings_factory
        self._ingestion_factory = ingestion_factory

    def accuracy_dashboard(self, workspace_id) -> dict:
        findings = self._findings(workspace_id)
        summary = self._summarize(findings)
        per_pattern = self._per_pattern(findings)
        per_source = self._per_source(findings)
        most_rejected = self._most_rejected(per_pattern)
        return {
            "summary": summary,
            "per_pattern": per_pattern,
            "per_source": per_source,
            "most_rejected": most_rejected,
        }

    def _findings(self, workspace_id) -> list:
        if self._findings_factory is None:
            return []
        svc = self._findings_factory(self.s)
        if not hasattr(svc, "list_for_workspace"):
            # Degrade to per-opportunity listing if the store is older.
            return self._findings_via_opportunities(workspace_id, svc)
        return svc.list_for_workspace(workspace_id)

    def _findings_via_opportunities(self, workspace_id, findings_svc) -> list:
        if self._ingestion_factory is None:
            return []
        ing = self._ingestion_factory(self.s)
        if not hasattr(ing, "list_opportunities") or not hasattr(findings_svc, "list"):
            return []
        findings: list = []
        for opp in ing.list_opportunities(workspace_id):
            findings.extend(findings_svc.list(workspace_id, str(opp.id)))
        return findings

    @staticmethod
    def _summarize(findings: list) -> dict:
        by_status = {s: 0 for s in _STATUSES}
        for f in findings:
            status = getattr(f, "review_status", "proposed") or "proposed"
            by_status[status] = by_status.get(status, 0) + 1

        accepted = by_status.get("accepted", 0) + by_status.get("edited", 0)
        rejected = by_status.get("rejected", 0)
        false_positive = by_status.get("false_positive", 0)
        denominator = accepted + rejected + false_positive
        precision = accepted / denominator if denominator else None

        return {
            "total_findings": len(findings),
            "by_status": by_status,
            "precision": precision,
            "recall": None,
            "false_positive_count": false_positive,
            "false_negative_count": None,
        }

    @staticmethod
    def _per_pattern(findings: list) -> list[dict]:
        buckets: dict[str, dict] = defaultdict(
            lambda: {
                "total": 0,
                "accepted": 0,
                "edited": 0,
                "rejected": 0,
                "false_positive": 0,
                "needs_clarification": 0,
                "proposed": 0,
            }
        )
        for f in findings:
            key = getattr(f, "pattern_id", None) or getattr(f, "kind", "unknown")
            kind = getattr(f, "kind", "unknown")
            bucket = buckets[key]
            bucket["kind"] = kind
            bucket["total"] += 1
            status = getattr(f, "review_status", "proposed") or "proposed"
            if status in bucket:
                bucket[status] += 1

        rows = []
        for pattern_id, b in sorted(buckets.items(), key=lambda x: -x[1]["total"]):
            accepted_plus = b["accepted"] + b["edited"]
            denom = accepted_plus + b["rejected"] + b["false_positive"]
            rows.append(
                {
                    "pattern_id": pattern_id,
                    "kind": b["kind"],
                    "total": b["total"],
                    "accepted": b["accepted"],
                    "edited": b["edited"],
                    "rejected": b["rejected"],
                    "false_positive": b["false_positive"],
                    "needs_clarification": b["needs_clarification"],
                    "proposed": b["proposed"],
                    "precision": accepted_plus / denom if denom else None,
                }
            )
        return rows

    @staticmethod
    def _per_source(findings: list) -> list[dict]:
        by_source: dict[str, Counter] = defaultdict(Counter)
        for f in findings:
            source = getattr(f, "producer", "unknown") or "unknown"
            status = getattr(f, "review_status", "proposed") or "proposed"
            by_source[source][status] += 1
            by_source[source]["total"] += 1

        rows = []
        for source, counts in sorted(by_source.items(), key=lambda x: -x[1]["total"]):
            accepted_plus = counts["accepted"] + counts["edited"]
            denom = accepted_plus + counts["rejected"] + counts["false_positive"]
            rows.append(
                {
                    "producer": source,
                    "total": counts["total"],
                    "accepted": counts["accepted"],
                    "edited": counts["edited"],
                    "rejected": counts["rejected"],
                    "false_positive": counts["false_positive"],
                    "needs_clarification": counts["needs_clarification"],
                    "proposed": counts["proposed"],
                    "precision": accepted_plus / denom if denom else None,
                }
            )
        return rows

    @staticmethod
    def _most_rejected(per_pattern: list[dict]) -> list[dict]:
        ranked = sorted(per_pattern, key=lambda r: -(r["rejected"] + r["false_positive"]))
        return [
            {"pattern_id": r["pattern_id"], "rejections": r["rejected"] + r["false_positive"]}
            for r in ranked
            if r["rejected"] + r["false_positive"] > 0
        ]

    def risk_summary(self, workspace_id) -> dict:
        findings = self._findings(workspace_id)
        risk = [f for f in findings if getattr(f, "producer", "unknown") != "boq"]
        by_severity: dict[str, int] = Counter()
        by_category: dict[str, int] = Counter()
        total_exposure = 0
        for f in risk:
            by_severity[getattr(f, "severity", "unknown")] += 1
            by_category[getattr(f, "category", "unknown")] += 1
            total_exposure += getattr(f, "amount_exposure", 0) or 0
        return {
            "total": len(risk),
            "by_severity": dict(by_severity),
            "by_category": dict(by_category),
            "total_exposure_minor": total_exposure,
        }

    def deadline_dashboard(self, workspace_id) -> dict:
        opportunities = []
        if self._ingestion_factory:
            ing = self._ingestion_factory(self.s)
            if hasattr(ing, "list_opportunities"):
                opportunities = ing.list_opportunities(workspace_id)
        now = datetime.now(UTC)
        buckets: dict[str, list[str]] = {
            "overdue": [], "7_days": [], "15_days": [], "30_days": [], "later": []
        }
        for opp in opportunities:
            due = getattr(opp, "submission_due", None)
            if due is None:
                buckets["later"].append(str(opp.id))
                continue
            if due.tzinfo is None:
                due = due.replace(tzinfo=UTC)
            delta = (due - now).days
            if delta < 0:
                buckets["overdue"].append(str(opp.id))
            elif delta <= 7:
                buckets["7_days"].append(str(opp.id))
            elif delta <= 15:
                buckets["15_days"].append(str(opp.id))
            elif delta <= 30:
                buckets["30_days"].append(str(opp.id))
            else:
                buckets["later"].append(str(opp.id))
        return {"now": now.isoformat(), "buckets": buckets}

    def boq_defect_summary(self, workspace_id) -> dict:
        findings = self._findings(workspace_id)
        boq = [f for f in findings if getattr(f, "producer", None) == "boq"]
        by_trade: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for f in boq:
            trades = getattr(f, "affected_trades", []) or ["unknown"]
            category = getattr(f, "category", "unknown")
            for trade in trades:
                by_trade[trade][category] += 1
        return {"total": len(boq), "by_trade": {k: dict(v) for k, v in by_trade.items()}}

    def plan_dashboard(
        self,
        workspace_id,
        opportunity_id,
        query: str,
        *,
        identity: dict | None = None,
        agent: PlanDashboardAgent | None = None,
    ) -> dict:
        """Generate an AI-structured dashboard for a tender/opportunity.

        All facts are pulled deterministically from the workspace; the LLM only
        decides how to visualize and summarize.
        """
        context = self._plan_context(workspace_id, opportunity_id)
        if context is None:
            raise AnalyticsError("opportunity_not_found")
        if agent is None:
            return {
                "title": "Dashboard (no model)",
                "summary": "Set TS_OPENROUTER_API_KEY to enable AI-generated visualizations.",
                "sections": [
                    {
                        "type": "text",
                        "title": "Facts",
                        "data": {"content": json.dumps(context, default=str, indent=2)},
                    }
                ],
                "citations": [],
            }
        return agent.generate(query, context, identity=identity)

    def _plan_context(self, workspace_id, opportunity_id) -> dict | None:
        opp = None
        if self._ingestion_factory:
            ing = self._ingestion_factory(self.s)
            if hasattr(ing, "get_opportunity"):
                opp = ing.get_opportunity(workspace_id, opportunity_id)
            if opp is None:
                return None

        deadlines: list = []
        docs: list = []
        if self._ingestion_factory:
            ing = self._ingestion_factory(self.s)
            if hasattr(ing, "list_deadlines"):
                deadlines = [
                    {
                        "kind": d.kind,
                        "due_at": d.due_at.isoformat() if d.due_at else None,
                        "page": d.source_page,
                        "confirmed": getattr(d, "confirmed", False),
                    }
                    for d in ing.list_deadlines(workspace_id, opportunity_id)
                ]
            if hasattr(ing, "list_documents"):
                docs = [
                    {
                        "filename": d.filename,
                        "kind": getattr(d, "kind", "other"),
                        "pages": getattr(d, "pages", None),
                    }
                    for d in ing.list_documents(workspace_id, opportunity_id)
                ]

        findings: list = []
        if self._findings_factory:
            find = self._findings_factory(self.s)
            if hasattr(find, "list"):
                findings = [
                    {
                        "severity": getattr(f, "severity", "unknown"),
                        "category": getattr(f, "category", "unknown"),
                        "title": getattr(f, "title", ""),
                        "producer": getattr(f, "producer", "unknown"),
                        "page": getattr(f, "source_page", None),
                        "amount_exposure": getattr(f, "amount_exposure", 0) or 0,
                    }
                    for f in find.list(workspace_id, opportunity_id)
                ]

        by_severity: Counter = Counter(f["severity"] for f in findings)
        by_category: Counter = Counter(f["category"] for f in findings)
        total_exposure = sum(f["amount_exposure"] for f in findings)

        return {
            "opportunity_title": getattr(opp, "title", None) if opp else None,
            "risk_summary": {
                "total": len(findings),
                "by_severity": dict(by_severity),
                "by_category": dict(by_category),
                "total_exposure_minor": total_exposure,
            },
            "deadlines": deadlines,
            "documents": docs,
            "sample_findings": findings[:20],
        }

    def export_report(self, workspace_id, filter_type: str, format: str) -> dict:
        if filter_type == "risk":
            rows = self._findings(workspace_id)
        elif filter_type == "boq":
            rows = [
                f for f in self._findings(workspace_id)
                if getattr(f, "producer", None) == "boq"
            ]
        elif filter_type == "deadlines":
            rows = []
            if self._ingestion_factory:
                ing = self._ingestion_factory(self.s)
                if hasattr(ing, "list_opportunities"):
                    rows = ing.list_opportunities(workspace_id)
        elif filter_type == "all":
            rows = self._findings(workspace_id)
        else:
            raise ValueError("invalid_filter")

        if format == "csv":
            return self._to_csv(rows, filter_type)
        if format == "xlsx":
            return self._to_xlsx(rows, filter_type)
        raise ValueError("invalid_format")

    def _to_csv(self, rows: list, kind: str) -> dict:
        output = io.StringIO()
        if kind == "deadlines":
            writer = csv.DictWriter(output, fieldnames=["id", "title", "submission_due"])
            writer.writeheader()
            for r in rows:
                writer.writerow(
                    {
                        "id": str(getattr(r, "id", "")),
                        "title": getattr(r, "title", ""),
                        "submission_due": (
                            getattr(r, "submission_due", "").isoformat()
                            if getattr(r, "submission_due", None)
                            else ""
                        ),
                    }
                )
        else:
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    "id", "kind", "category", "severity", "title", "producer",
                    "amount_exposure",
                ],
            )
            writer.writeheader()
            for r in rows:
                writer.writerow(
                    {
                        "id": str(getattr(r, "id", "")),
                        "kind": getattr(r, "kind", ""),
                        "category": getattr(r, "category", ""),
                        "severity": getattr(r, "severity", ""),
                        "title": getattr(r, "title", ""),
                        "producer": getattr(r, "producer", ""),
                        "amount_exposure": getattr(r, "amount_exposure", 0),
                    }
                )
        return {
            "content": output.getvalue().encode("utf-8"),
            "content_type": "text/csv",
            "filename": f"{kind}_report.csv",
        }

    def _to_xlsx(self, rows: list, kind: str) -> dict:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Report"
        if kind == "deadlines":
            ws.append(["id", "title", "submission_due"])
            for r in rows:
                ws.append(
                    [
                        str(getattr(r, "id", "")),
                        getattr(r, "title", ""),
                        (
                            getattr(r, "submission_due", "").isoformat()
                            if getattr(r, "submission_due", None)
                            else ""
                        ),
                    ]
                )
        else:
            ws.append([
                "id", "kind", "category", "severity", "title", "producer",
                "amount_exposure",
            ])
            for r in rows:
                ws.append(
                    [
                        str(getattr(r, "id", "")),
                        getattr(r, "kind", ""),
                        getattr(r, "category", ""),
                        getattr(r, "severity", ""),
                        getattr(r, "title", ""),
                        getattr(r, "producer", ""),
                        getattr(r, "amount_exposure", 0),
                    ]
                )
        output = io.BytesIO()
        wb.save(output)
        return {
            "content": output.getvalue(),
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "filename": f"{kind}_report.xlsx",
        }

    # -----------------------------------------------------------------------
    # Plan dashboard templates, snapshots, and export (TS-191)
    # -----------------------------------------------------------------------

    PLAN_TEMPLATES = {
        "risk-severity": {
            "id": "risk-severity",
            "name": "Risk severity distribution",
            "query": (
                "Show the risk severity distribution and total exposure as KPIs and a pie chart."
            ),
        },
        "deadline-timeline": {
            "id": "deadline-timeline",
            "name": "Deadline timeline",
            "query": "Show all upcoming deadlines in a table and a Gantt-style sequence diagram.",
        },
        "boq-defects": {
            "id": "boq-defects",
            "name": "BOQ defect summary",
            "query": "Summarise BOQ defects by trade and category in a table and bar chart.",
        },
        "bid-readiness": {
            "id": "bid-readiness",
            "name": "Bid readiness overview",
            "query": (
                "Build a bid readiness dashboard with risk count, deadline countdown, and "
                "exposure KPIs."
            ),
        },
    }

    @classmethod
    def list_plan_templates(cls) -> list[dict]:
        return list(cls.PLAN_TEMPLATES.values())

    @staticmethod
    def _to_uuid(value) -> uuid.UUID:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))

    def list_plan_snapshots(self, workspace_id, user_id) -> list[dict]:
        rows = self.s.execute(
            select(PlanSnapshot).where(
                PlanSnapshot.workspace_id == self._to_uuid(workspace_id),
                PlanSnapshot.user_id == self._to_uuid(user_id),
            )
        ).scalars().all()
        return [
            {
                "id": str(r.id),
                "opportunity_id": str(r.opportunity_id),
                "title": r.title,
                "query": r.query,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def save_plan_snapshot(
        self,
        workspace_id,
        user_id,
        opportunity_id,
        title: str,
        query: str,
        dashboard: dict,
    ) -> dict:
        if not title.strip():
            raise AnalyticsError("title is required")
        snapshot = PlanSnapshot(
            workspace_id=self._to_uuid(workspace_id),
            user_id=self._to_uuid(user_id),
            opportunity_id=self._to_uuid(opportunity_id),
            title=title.strip(),
            query=query.strip(),
            dashboard=dashboard,
        )
        self.s.add(snapshot)
        self.s.commit()
        return {
            "id": str(snapshot.id),
            "opportunity_id": str(snapshot.opportunity_id),
            "title": snapshot.title,
            "query": snapshot.query,
            "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        }

    def get_plan_snapshot(self, workspace_id, user_id, snapshot_id: str) -> dict:
        row = self.s.get(PlanSnapshot, uuid.UUID(snapshot_id))
        if (
            row is None
            or row.workspace_id != self._to_uuid(workspace_id)
            or row.user_id != self._to_uuid(user_id)
        ):
            raise AnalyticsError("snapshot_not_found")
        return {
            "id": str(row.id),
            "opportunity_id": str(row.opportunity_id),
            "title": row.title,
            "query": row.query,
            "dashboard": row.dashboard,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def delete_plan_snapshot(self, workspace_id, user_id, snapshot_id: str) -> None:
        row = self.s.get(PlanSnapshot, uuid.UUID(snapshot_id))
        if (
            row is None
            or row.workspace_id != self._to_uuid(workspace_id)
            or row.user_id != self._to_uuid(user_id)
        ):
            raise AnalyticsError("snapshot_not_found")
        self.s.delete(row)
        self.s.commit()

    def export_plan_dashboard(
        self,
        workspace_id,
        user_id,
        snapshot_id: str,
        format: str,
    ) -> dict:
        snapshot = self.get_plan_snapshot(workspace_id, user_id, snapshot_id)
        exporter = PlanDashboardExporter()
        opportunity_title = snapshot["dashboard"].get("opportunity_title", "")
        content = exporter.export(snapshot["dashboard"], format, opportunity_title)
        if format == "pdf":
            content_type = "application/pdf"
            filename = f"{snapshot['title'] or 'plan'}.pdf"
        elif format == "pptx":
            content_type = (
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )
            filename = f"{snapshot['title'] or 'plan'}.pptx"
        else:
            raise AnalyticsError("invalid_format")
        return {"content": content, "content_type": content_type, "filename": filename}
