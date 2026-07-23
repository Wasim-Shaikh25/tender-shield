"""IngestionService — owns opportunities + documents, runs rules-first
classification, and produces the missing-doc checklist.

Consumes `rulepacks.loader` as a lazily-resolved soft dependency (doc-type
anchors + expected-doc set). Queries are scoped by org_id explicitly (defense
in depth alongside RLS) so isolation holds on any backend."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ingestion.classify import classify_text, missing_documents
from app.modules.ingestion.models import Document, Opportunity

_FALLBACK_ANCHORS = {
    "nit": [r"NOTICE\s+INVITING\s+TENDER", r"\bNIT\s*No"],
    "gcc": [r"GENERAL\s+CONDITIONS\s+OF\s+CONTRACT"],
    "boq": [r"BILL\s+OF\s+QUANTIT", r"SCHEDULE\s+OF\s+QUANTIT"],
}
_FALLBACK_EXPECTED = ["nit", "gcc", "boq"]


class IngestionService:
    def __init__(
        self,
        session: Session,
        *,
        loader_provider: Callable[[], object | None] = lambda: None,
        publish: Callable[[str, dict], object] = lambda event, payload: None,
        pack_id: str = "in-works",
    ):
        self.s = session
        self._loader_provider = loader_provider
        self._publish = publish
        self._pack_id = pack_id

    # ---- rule-pack config (soft dep, graceful fallback) -------------------
    def _anchors(self) -> dict[str, list[str]]:
        loader = self._loader_provider()
        if not loader:
            return _FALLBACK_ANCHORS
        pack = loader.get_pack(self._pack_id)
        return {name: dt.anchors for name, dt in pack.doc_types.items()}

    def _expected(self) -> list[str]:
        loader = self._loader_provider()
        if not loader:
            return _FALLBACK_EXPECTED
        return loader.get_pack(self._pack_id).expected_documents or _FALLBACK_EXPECTED

    # ---- opportunities ----------------------------------------------------
    def create_opportunity(self, org_id, title: str, **fields) -> Opportunity:
        opp = Opportunity(org_id=uuid.UUID(str(org_id)), title=title, **fields)
        self.s.add(opp)
        self.s.commit()
        self._publish("opportunity.created", {"opportunity_id": str(opp.id)})
        return opp

    def get_opportunity(self, org_id, opportunity_id) -> Opportunity | None:
        return self.s.scalar(
            select(Opportunity).where(
                Opportunity.id == uuid.UUID(str(opportunity_id)),
                Opportunity.org_id == uuid.UUID(str(org_id)),
            )
        )

    # ---- documents --------------------------------------------------------
    def register_document(
        self, org_id, opportunity_id, filename: str, sample_text: str = "", **fields
    ) -> Document:
        """Classify (rules-first) and persist a document for an opportunity."""
        kind = classify_text(sample_text, self._anchors()) or "other"
        doc = Document(
            org_id=uuid.UUID(str(org_id)),
            opportunity_id=uuid.UUID(str(opportunity_id)),
            filename=filename,
            kind=kind,
            **fields,
        )
        self.s.add(doc)
        self.s.commit()
        self._publish(
            "document.classified", {"document_id": str(doc.id), "kind": kind}
        )
        return doc

    def list_documents(self, org_id, opportunity_id) -> list[Document]:
        return list(
            self.s.scalars(
                select(Document).where(
                    Document.opportunity_id == uuid.UUID(str(opportunity_id)),
                    Document.org_id == uuid.UUID(str(org_id)),
                )
            )
        )

    def missing_doc_report(self, org_id, opportunity_id) -> dict:
        present = [d.kind for d in self.list_documents(org_id, opportunity_id)]
        missing = missing_documents(present, self._expected())
        return {"present": sorted(set(present)), "missing": missing, "expected": self._expected()}
