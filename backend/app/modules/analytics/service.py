"""AnalyticsService — internal accuracy dashboard.

Read-only aggregator over the findings store. Precision/recall are explicitly
proxies where real golden labels are absent.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable

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

    def accuracy_dashboard(self, org_id) -> dict:
        findings = self._findings(org_id)
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

    def _findings(self, org_id) -> list:
        if self._findings_factory is None:
            return []
        svc = self._findings_factory(self.s)
        if not hasattr(svc, "list_for_org"):
            # Degrade to per-opportunity listing if the store is older.
            return self._findings_via_opportunities(org_id, svc)
        return svc.list_for_org(org_id)

    def _findings_via_opportunities(self, org_id, findings_svc) -> list:
        if self._ingestion_factory is None:
            return []
        ing = self._ingestion_factory(self.s)
        if not hasattr(ing, "list_opportunities") or not hasattr(findings_svc, "list"):
            return []
        findings: list = []
        for opp in ing.list_opportunities(org_id):
            findings.extend(findings_svc.list(org_id, str(opp.id)))
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
            rows.append({
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
            })
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
            rows.append({
                "producer": source,
                "total": counts["total"],
                "accepted": counts["accepted"],
                "edited": counts["edited"],
                "rejected": counts["rejected"],
                "false_positive": counts["false_positive"],
                "needs_clarification": counts["needs_clarification"],
                "proposed": counts["proposed"],
                "precision": accepted_plus / denom if denom else None,
            })
        return rows

    @staticmethod
    def _most_rejected(per_pattern: list[dict]) -> list[dict]:
        ranked = sorted(per_pattern, key=lambda r: -(r["rejected"] + r["false_positive"]))
        return [
            {"pattern_id": r["pattern_id"], "rejections": r["rejected"] + r["false_positive"]}
            for r in ranked
            if r["rejected"] + r["false_positive"] > 0
        ]
