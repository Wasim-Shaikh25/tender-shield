"""AnalyticsService — internal accuracy dashboard.

Read-only aggregator over the findings store. Precision/recall are explicitly
proxies where real golden labels are absent.
"""

from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

_STATUSES = {"proposed", "accepted", "edited", "rejected", "false_positive", "needs_clarification"}


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
