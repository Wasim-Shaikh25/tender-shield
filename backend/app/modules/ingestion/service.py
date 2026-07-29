"""IngestionService — owns opportunities + documents, runs rules-first
classification, and produces the missing-doc checklist.

Consumes `rulepacks.loader` as a lazily-resolved soft dependency (doc-type
anchors + expected-doc set). Queries are scoped by workspace_id explicitly (defense
in depth alongside RLS) so isolation holds on any backend."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ingestion.classify import classify_text, missing_documents
from app.modules.ingestion.deadlines import extract_deadlines
from app.modules.ingestion.doc_text import DocTextService, persist_chunks
from app.modules.ingestion.models import Clause, Deadline, Document, Opportunity
from app.modules.ingestion.segment import segment_clauses

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
    def create_opportunity(self, workspace_id, title: str, **fields) -> Opportunity:
        opp = Opportunity(workspace_id=uuid.UUID(str(workspace_id)), title=title, **fields)
        self.s.add(opp)
        self.s.commit()
        self._publish("opportunity.created", {"opportunity_id": str(opp.id)})
        return opp

    def list_opportunities(self, workspace_id) -> list[Opportunity]:
        return list(
            self.s.scalars(
                select(Opportunity)
                .where(Opportunity.workspace_id == uuid.UUID(str(workspace_id)))
                .order_by(Opportunity.created_at.desc())
            )
        )

    def get_opportunity(self, workspace_id, opportunity_id) -> Opportunity | None:
        return self.s.scalar(
            select(Opportunity).where(
                Opportunity.id == uuid.UUID(str(opportunity_id)),
                Opportunity.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )

    def extract_text(self, filename: str, data: bytes) -> str:
        """Digital text extraction (no persistence) for callers like baseline."""
        from app.modules.ingestion.extract import extract_text as _extract_text

        return _extract_text(filename, data)

    # ---- documents --------------------------------------------------------
    def register_document(
        self, workspace_id, opportunity_id, filename: str, sample_text: str = "", **fields
    ) -> Document:
        """Classify (rules-first) and persist a document for an opportunity."""
        kind = classify_text(sample_text, self._anchors()) or "other"
        doc = Document(
            workspace_id=uuid.UUID(str(workspace_id)),
            opportunity_id=uuid.UUID(str(opportunity_id)),
            filename=filename,
            kind=kind,
            **fields,
        )
        self.s.add(doc)
        self.s.commit()
        self._publish("document.classified", {"document_id": str(doc.id), "kind": kind})
        if sample_text.strip():
            self._segment(doc, sample_text)
            self._extract_deadlines(doc, sample_text)
            persist_chunks(self.s, doc.workspace_id, doc.opportunity_id, doc.id, sample_text)
        return doc

    def _extract_deadlines(self, doc: Document, text: str) -> int:
        """Deterministic deadline extraction (Doc §6.2). Sets the opportunity's
        submission_due from the earliest submission deadline so the board's
        countdown wall lights up."""
        count = 0
        earliest_submission = None
        for ex in extract_deadlines(text):
            self.s.add(
                Deadline(
                    workspace_id=doc.workspace_id,
                    opportunity_id=doc.opportunity_id,
                    kind=ex.kind,
                    due_at=ex.due_at,
                    description=ex.description,
                    source_page=ex.source_page,
                    source_quote=ex.source_quote,
                )
            )
            count += 1
            if ex.kind == "submission" and ex.due_at is not None:
                if earliest_submission is None or ex.due_at < earliest_submission:
                    earliest_submission = ex.due_at
        if earliest_submission is not None:
            opp = self.get_opportunity(doc.workspace_id, doc.opportunity_id)
            if opp is not None:
                opp.submission_due = earliest_submission
        self.s.commit()
        if count:
            self._publish("deadlines.extracted", {"document_id": str(doc.id), "count": count})
        return count

    def list_deadlines(self, workspace_id, opportunity_id) -> list[Deadline]:
        return list(
            self.s.scalars(
                select(Deadline).where(
                    Deadline.opportunity_id == uuid.UUID(str(opportunity_id)),
                    Deadline.workspace_id == uuid.UUID(str(workspace_id)),
                )
            )
        )

    def confirm_deadline(self, workspace_id, deadline_id) -> Deadline | None:
        dl = self.s.scalar(
            select(Deadline).where(
                Deadline.id == uuid.UUID(str(deadline_id)),
                Deadline.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )
        if dl is not None:
            dl.confirmed = True
            self.s.commit()
        return dl

    def _segment(self, doc: Document, text: str) -> int:
        """Segment a document's text into clause rows (Doc §3.2)."""
        count = 0
        for seg in segment_clauses(text):
            self.s.add(
                Clause(
                    workspace_id=doc.workspace_id,
                    document_id=doc.id,
                    opportunity_id=doc.opportunity_id,
                    clause_ref=seg.clause_ref,
                    heading=seg.heading,
                    text=seg.text,
                    page_from=seg.page_from,
                    page_to=seg.page_to,
                    cross_refs=seg.cross_refs,
                )
            )
            count += 1
        self.s.commit()
        if count:
            self._publish("clauses.segmented", {"document_id": str(doc.id), "count": count})
        return count

    def get_document(self, workspace_id, document_id) -> Document | None:
        return self.s.scalar(
            select(Document).where(
                Document.id == uuid.UUID(str(document_id)),
                Document.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )

    def list_clauses(self, workspace_id, opportunity_id) -> list[Clause]:
        return list(
            self.s.scalars(
                select(Clause).where(
                    Clause.opportunity_id == uuid.UUID(str(opportunity_id)),
                    Clause.workspace_id == uuid.UUID(str(workspace_id)),
                )
            )
        )

    def list_clauses_for_document(self, workspace_id, document_id) -> list[Clause]:
        return list(
            self.s.scalars(
                select(Clause).where(
                    Clause.document_id == uuid.UUID(str(document_id)),
                    Clause.workspace_id == uuid.UUID(str(workspace_id)),
                )
            )
        )

    def list_documents(self, workspace_id, opportunity_id) -> list[Document]:
        return list(
            self.s.scalars(
                select(Document).where(
                    Document.opportunity_id == uuid.UUID(str(opportunity_id)),
                    Document.workspace_id == uuid.UUID(str(workspace_id)),
                )
            )
        )

    def missing_doc_report(self, workspace_id, opportunity_id) -> dict:
        present = [d.kind for d in self.list_documents(workspace_id, opportunity_id)]
        missing = missing_documents(present, self._expected())
        return {"present": sorted(set(present)), "missing": missing, "expected": self._expected()}

    def get_doc_text(self, workspace_id, document_id, page: int | None = None):
        """Page-level text access used by crossref, assistant, and search."""
        svc = DocTextService(self.s)
        if page is not None:
            return {"page": page, "text": svc.text_for_page(workspace_id, document_id, page)}
        return {"pages": svc.text_for_document(workspace_id, document_id)}
