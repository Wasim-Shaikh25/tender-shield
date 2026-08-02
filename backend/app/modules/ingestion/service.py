"""IngestionService — owns opportunities + documents, runs rules-first
classification, and produces the missing-doc checklist.

Consumes `rulepacks.loader` as a lazily-resolved soft dependency (doc-type
anchors + expected-doc set). Queries are scoped by workspace_id explicitly (defense
in depth alongside RLS) so isolation holds on any backend."""

from __future__ import annotations

import difflib
import hashlib
import re
import uuid
from collections.abc import Callable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.ingestion.classify import classify_text, missing_documents
from app.modules.ingestion.deadlines import extract_deadlines
from app.modules.ingestion.doc_text import (
    DocTextService,
    detect_language,
    persist_chunks,
    translate_summary,
)
from app.modules.ingestion.models import Clause, Deadline, DefinedTerm, Document, Opportunity
from app.modules.ingestion.segment import segment_clauses, segment_defined_terms

_FALLBACK_ANCHORS = {
    "nit": [r"NOTICE\s+INVITING\s+TENDER", r"\bNIT\s*No"],
    "gcc": [r"GENERAL\s+CONDITIONS\s+OF\s+CONTRACT"],
    "boq": [r"BILL\s+OF\s+QUANTIT", r"SCHEDULE\s+OF\s+QUANTIT"],
}
_FALLBACK_EXPECTED = ["nit", "gcc", "boq"]

# Filename markers that indicate an addendum/revision.
_ADDENDUM_KEYWORDS = (
    "addendum",
    "addenda",
    "amendment",
    "amended",
    "revised",
    "revision",
    "rev",
    "corrigendum",
    "errata",
    "supplement",
    "correction",
    "clarification",
)
# Version suffixes like _v2, _2, rev2, version 3 (deliberately permissive).
_VERSION_RE = re.compile(
    r"[\s\-_]?(?:v|ver|version|rev|revision)\s*([0-9]+)"
    r"|[\s\-_]([0-9]+)(?=[\s\-_]|$)",
    re.IGNORECASE,
)


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
        """Classify (rules-first), detect duplicates/addenda, and persist a document."""
        kind = classify_text(sample_text, self._anchors()) or "other"
        sha256 = fields.pop("sha256", "") or ""
        if not sha256 and sample_text:
            sha256 = hashlib.sha256(sample_text.encode("utf-8")).hexdigest()

        duplicate = self._find_duplicate(workspace_id, opportunity_id, sha256)
        doc = Document(
            workspace_id=uuid.UUID(str(workspace_id)),
            opportunity_id=uuid.UUID(str(opportunity_id)),
            filename=filename,
            kind=kind,
            sha256=sha256,
            **fields,
        )
        if duplicate is not None:
            doc.meta = {"duplicate_of": str(duplicate.id), "addendum": False}
            doc.ocr_status = "duplicate"
            self.s.add(doc)
            self.s.commit()
            return doc

        is_addendum, addendum_reason = self._detect_addendum(filename)
        if is_addendum and not doc.supersedes:
            superseded = self._find_superseded(workspace_id, opportunity_id, kind, filename)
            if superseded is not None:
                doc.supersedes = superseded.id
                doc.meta = {
                    "addendum": True,
                    "addendum_reason": addendum_reason,
                    "addendum_changes": [],
                }

        self.s.add(doc)
        self.s.commit()
        self._publish("document.classified", {"document_id": str(doc.id), "kind": kind})
        if sample_text.strip():
            self.process_text(doc, sample_text, ocr_status=fields.get("ocr_status") or "done")
            if is_addendum and doc.supersedes:
                changes = self._addendum_changes(doc, doc.supersedes)
                doc.meta["addendum_changes"] = changes
                self.s.commit()
        return doc

    def process_text(self, doc: Document, text: str, ocr_status: str = "done") -> None:
        """Segment clauses, extract deadlines, persist chunks, glossary, and update metadata."""
        doc.kind = classify_text(text, self._anchors()) or doc.kind
        doc.ocr_status = ocr_status
        self._segment(doc, text)
        self._extract_deadlines(doc, text)
        self._extract_defined_terms(doc, text)
        persist_chunks(self.s, doc.workspace_id, doc.opportunity_id, doc.id, text)
        doc.meta = {**(doc.meta or {}), "language": detect_language(text)}
        if doc.meta.get("language") != "en":
            from app.core.llm import openrouter_client

            summary = translate_summary(
                text[:5000], doc.meta["language"], client=openrouter_client("ingestion.translate")
            )
            if summary:
                doc.meta["translation_summary"] = summary
        self.s.commit()

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

    def confirm_deadline(
        self, workspace_id, opportunity_id, deadline_id
    ) -> Deadline | None:
        dl = self.s.scalar(
            select(Deadline).where(
                Deadline.id == uuid.UUID(str(deadline_id)),
                Deadline.workspace_id == uuid.UUID(str(workspace_id)),
                Deadline.opportunity_id == uuid.UUID(str(opportunity_id)),
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

    # ---- addendum / duplicate detection -----------------------------------
    def _detect_addendum(self, filename: str) -> tuple[bool, str]:
        name = filename.lower()
        if any(k in name for k in _ADDENDUM_KEYWORDS):
            return True, "keyword"
        if _VERSION_RE.search(name):
            return True, "version_suffix"
        return False, ""

    def _base_filename(self, filename: str) -> str:
        """Strip version/addendum suffixes so addenda match their base doc."""
        base = filename.lower().rsplit(".", 1)[0]
        for keyword in _ADDENDUM_KEYWORDS:
            base = re.sub(rf"[\s\-_]?{keyword}[\s\-_]?[0-9]*", "", base, flags=re.IGNORECASE)
        base = _VERSION_RE.sub("", base)
        return re.sub(r"[\s\-_]+", " ", base).strip()

    def _find_duplicate(self, workspace_id, opportunity_id, sha256: str) -> Document | None:
        if not sha256:
            return None
        return self.s.scalar(
            select(Document).where(
                Document.workspace_id == uuid.UUID(str(workspace_id)),
                Document.opportunity_id == uuid.UUID(str(opportunity_id)),
                Document.sha256 == sha256,
            )
        )

    def _find_superseded(
        self, workspace_id, opportunity_id, kind: str, filename: str
    ) -> Document | None:
        base = self._base_filename(filename)
        rows = list(
            self.s.scalars(
                select(Document)
                .where(
                    Document.workspace_id == uuid.UUID(str(workspace_id)),
                    Document.opportunity_id == uuid.UUID(str(opportunity_id)),
                    Document.kind == kind,
                    Document.id != None,  # noqa: E711
                )
                .order_by(Document.created_at.desc())
            )
        )
        for row in rows:
            if row.supersedes is None and base and base in self._base_filename(row.filename):
                return row
        # Fall back to the most recent document of the same kind.
        for row in rows:
            if row.supersedes is None:
                return row
        return rows[0] if rows else None

    def _addendum_changes(self, new_doc: Document, superseded_id: uuid.UUID) -> list[dict]:
        """Clause-level diff of an addendum against the document it supersedes."""
        old_clauses = {
            (c.clause_ref or ""): c.text
            for c in self.list_clauses_for_document(new_doc.workspace_id, superseded_id)
        }
        new_clauses = {
            (c.clause_ref or ""): c.text
            for c in self.list_clauses_for_document(new_doc.workspace_id, new_doc.id)
        }
        changes: list[dict] = []
        for ref in sorted(set(old_clauses) | set(new_clauses)):
            old_text = old_clauses.get(ref)
            new_text = new_clauses.get(ref)
            if old_text is None:
                preview = new_text[:200] if new_text else ""
                changes.append({"clause_ref": ref, "status": "added", "diff": preview})
            elif new_text is None:
                changes.append({"clause_ref": ref, "status": "removed"})
            elif old_text != new_text:
                diff = list(
                    difflib.unified_diff(
                        old_text.splitlines(), new_text.splitlines(), lineterm=""
                    )
                )
                changes.append({"clause_ref": ref, "status": "modified", "diff_lines": diff[:20]})
        return changes

    def _extract_defined_terms(self, doc: Document, text: str) -> int:
        """Extract 'X means Y' definitions and persist them as an opportunity glossary."""
        self.s.execute(
            delete(DefinedTerm).where(
                DefinedTerm.document_id == doc.id,
                DefinedTerm.workspace_id == doc.workspace_id,
            )
        )
        count = 0
        for seg in segment_defined_terms(text):
            self.s.add(
                DefinedTerm(
                    workspace_id=doc.workspace_id,
                    opportunity_id=doc.opportunity_id,
                    document_id=doc.id,
                    term=seg.term,
                    definition=seg.definition,
                    source_quote=seg.source_quote,
                    source_clause_ref=seg.source_clause_ref,
                )
            )
            count += 1
        self.s.commit()
        if count:
            self._publish("defined_terms.extracted", {"document_id": str(doc.id), "count": count})
        return count

    def list_defined_terms(
        self, workspace_id, opportunity_id, document_id=None
    ) -> list[DefinedTerm]:
        stmt = select(DefinedTerm).where(
            DefinedTerm.workspace_id == uuid.UUID(str(workspace_id)),
            DefinedTerm.opportunity_id == uuid.UUID(str(opportunity_id)),
        )
        if document_id is not None:
            stmt = stmt.where(DefinedTerm.document_id == uuid.UUID(str(document_id)))
        return list(self.s.scalars(stmt.order_by(DefinedTerm.term)))

    def get_document(self, workspace_id, document_id) -> Document | None:
        return self.s.scalar(
            select(Document).where(
                Document.id == uuid.UUID(str(document_id)),
                Document.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )

    def list_clauses(
        self, workspace_id, opportunity_id, *, limit: int | None = None
    ) -> list[Clause]:
        stmt = (
            select(Clause)
            .where(
                Clause.opportunity_id == uuid.UUID(str(opportunity_id)),
                Clause.workspace_id == uuid.UUID(str(workspace_id)),
            )
            .order_by(Clause.id)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.s.scalars(stmt))

    def list_clauses_for_document(self, workspace_id, document_id) -> list[Clause]:
        return list(
            self.s.scalars(
                select(Clause).where(
                    Clause.document_id == uuid.UUID(str(document_id)),
                    Clause.workspace_id == uuid.UUID(str(workspace_id)),
                )
            )
        )

    def list_documents(
        self, workspace_id, opportunity_id, *, limit: int | None = None
    ) -> list[Document]:
        stmt = (
            select(Document)
            .where(
                Document.opportunity_id == uuid.UUID(str(opportunity_id)),
                Document.workspace_id == uuid.UUID(str(workspace_id)),
            )
            .order_by(Document.id)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.s.scalars(stmt))

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
