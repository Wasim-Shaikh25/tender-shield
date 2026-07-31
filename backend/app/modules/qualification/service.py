"""QualificationService — extracts eligibility criteria from an opportunity's
clauses and publishes `qualification_gap` findings through the findings store.

Consumes `ingestion.service_factory` and `findings.store_factory` via the registry.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.contracts.findings import Finding, FindingKind, FindingSource, Severity
from app.core.provenance import (
    ProvenanceStamp,
    document_set_hash,
    get_engine_version,
    stamp_findings,
)


@dataclass
class QualificationCriterion:
    key: str
    label: str
    status: str  # met | not_met | unknown
    evidence: str
    source_page: int | None
    source_quote: str
    action_required: str
    document_id: str | None = None


_CRITERIA_CONFIG: list[dict[str, Any]] = [
    {
        "key": "minimum_turnover",
        "label": "Minimum turnover",
        "keywords": [
            "minimum turnover",
            "average annual turnover",
            "turnover of the bidder",
        ],
    },
    {
        "key": "similar_project_experience",
        "label": "Similar project experience",
        "keywords": [
            "similar work",
            "similar experience",
            "similar nature",
            "similar works",
        ],
    },
    {
        "key": "equipment_requirements",
        "label": "Equipment requirements",
        "keywords": [
            "equipment",
            "machinery",
            "plant and equipment",
        ],
    },
    {
        "key": "engineer_requirements",
        "label": "Engineer requirements",
        "keywords": [
            "engineer",
            "technical personnel",
            "project manager",
        ],
    },
    {
        "key": "certifications",
        "label": "Certifications",
        "keywords": [
            "certification",
            "iso",
            "certificate",
        ],
    },
    {
        "key": "emd_amount",
        "label": "EMD amount",
        "keywords": [
            "earnest money",
            "emd",
        ],
    },
    {
        "key": "bid_security",
        "label": "Bid security",
        "keywords": [
            "bid security",
            "bid guarantee",
            "security deposit",
        ],
    },
    {
        "key": "experience_years",
        "label": "Experience years",
        "keywords": [
            "years of experience",
            "experience of at least",
            "minimum experience",
        ],
    },
]


def _build_evidence(clause: dict, keyword: str) -> tuple[str, int | None, str]:
    text = clause.get("text", "")
    page = clause.get("page_from")
    # Pull a window around the keyword.
    low = text.lower()
    idx = low.find(keyword)
    if idx == -1:
        quote = text[:200]
        return quote, page, quote
    start = max(0, idx - 60)
    end = min(len(text), idx + len(keyword) + 140)
    quote = text[start:end].strip()[:200]
    return quote, page, quote


class QualificationService:
    PRODUCER = "qualification"

    def __init__(
        self,
        session: Session,
        *,
        ingestion_factory: Callable[[Session], object] | None = None,
        store_factory: Callable[[Session], object] | None = None,
    ):
        self.s = session
        self._ingestion_factory = ingestion_factory
        self._store_factory = store_factory

    def _ingestion(self) -> object | None:
        if self._ingestion_factory is None:
            return None
        return self._ingestion_factory(self.s)

    def _store(self) -> object | None:
        if self._store_factory is None:
            return None
        return self._store_factory(self.s)

    def build_matrix(self, workspace_id, opportunity_id) -> list[QualificationCriterion]:
        svc = self._ingestion()
        if svc is None:
            return []

        clauses = svc.list_clauses(workspace_id, opportunity_id)
        records: list[QualificationCriterion] = []

        for cfg in _CRITERIA_CONFIG:
            found = None
            keyword = ""
            for clause in clauses:
                clause_text = (clause.text or "").lower()
                for kw in cfg["keywords"]:
                    if kw in clause_text:
                        found = clause
                        keyword = kw
                        break
                if found:
                    break

            if found is None:
                # A missing criterion is "unknown" (needs human review), not a
                # hard "not_met" failure; severity will be MEDIUM, not HIGH.
                records.append(
                    QualificationCriterion(
                        key=cfg["key"],
                        label=cfg["label"],
                        status="unknown",
                        evidence=f"{cfg['label']} not found in the tender documents.",
                        source_page=None,
                        source_quote="",
                        action_required=(
                            f"Confirm whether {cfg['label'].lower()} is required"
                            " and supply missing evidence."
                        ),
                    )
                )
                continue

            quote, page, source_quote = _build_evidence(
                {
                    "text": found.text,
                    "page_from": found.page_from,
                    "document_id": str(found.document_id),
                },
                keyword,
            )
            records.append(
                QualificationCriterion(
                    key=cfg["key"],
                    label=cfg["label"],
                    status="unknown",
                    evidence=quote,
                    source_page=page,
                    source_quote=source_quote,
                    action_required=(
                        f"Verify the organization's {cfg['label'].lower()}"
                        " against this requirement."
                    ),
                    document_id=str(found.document_id),
                )
            )

        return records

    def _document_hash(self, workspace_id, opportunity_id) -> str:
        ingestion = self._ingestion()
        if ingestion is None:
            return ""
        docs = ingestion.list_documents(workspace_id, opportunity_id)
        return document_set_hash([d.sha256 for d in docs if d.sha256])

    def run_opportunity(self, workspace_id, opportunity_id) -> list[QualificationCriterion]:
        matrix = self.build_matrix(workspace_id, opportunity_id)
        findings = [_to_finding(c) for c in matrix]
        stamp = ProvenanceStamp(
            rulepack_version="builtin",
            model_id="none",
            document_hash=self._document_hash(workspace_id, opportunity_id),
            engine_version=get_engine_version(),
        )
        findings = stamp_findings(findings, stamp)
        if self._store is not None and findings:
            self._store().replace_for_producer(
                workspace_id, opportunity_id, self.PRODUCER, findings
            )
        return matrix


def _to_finding(c: QualificationCriterion) -> Finding:
    severity = Severity.HIGH if c.status == "not_met" else Severity.MEDIUM
    doc_id = uuid.UUID(c.document_id) if c.document_id else None
    return Finding(
        kind=FindingKind.QUALIFICATION_GAP,
        category="qualification",
        severity=severity,
        title=f"{c.label} — {c.status}",
        detail=c.evidence,
        source=FindingSource.DETERMINISTIC_CHECK,
        source_page=c.source_page,
        source_quote=c.source_quote,
        suggested_action=c.action_required,
        pattern_id=c.key,
        document_id=doc_id,
        explanation={"status": c.status, "key": c.key, "label": c.label},
    )
