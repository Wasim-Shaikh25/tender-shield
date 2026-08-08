"""CrossRefService — search clauses across documents and diff document versions.

Consumes ingestion via registry; no imports of other modules (CLAUDE.md §2)."""

from __future__ import annotations

import difflib
import re

from app.modules.crossref.contradictions import (
    DEFAULT_PRECEDENCE,
    Contradiction,
    find_contradictions,
)
from app.modules.crossref.facts import CanonicalFact


class CrossRefService:
    def __init__(
        self, session, *, ingestion_factory=None, rulepacks_loader=None, pack_id="in-works"
    ):
        self.s = session
        self._ingestion_factory = ingestion_factory
        self._rulepacks_loader = rulepacks_loader
        self._pack_id = pack_id

    def _ingestion(self):
        return self._ingestion_factory(self.s) if self._ingestion_factory else None

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-z]+", text.lower()))

    def search(self, workspace_id, opportunity_id, query: str, limit: int = 20) -> list[dict]:
        svc = self._ingestion()
        if svc is None:
            return []
        query_tokens = self._tokens(query)
        if not query_tokens:
            return []

        # Fetch a bounded candidate set from the DB; score in memory and return top `limit`.
        candidate_limit = min(max(limit * 10, 100), 1000)
        docs = {
            str(d.id): d
            for d in svc.list_documents(workspace_id, opportunity_id, limit=candidate_limit)
        }
        clauses = svc.list_clauses(workspace_id, opportunity_id, limit=candidate_limit)

        scored = []
        for c in clauses:
            text = " ".join(filter(None, [c.heading, c.text]))
            clause_tokens = self._tokens(text)
            if not clause_tokens:
                continue
            overlap = len(query_tokens & clause_tokens)
            if overlap == 0:
                continue
            # Simple Jaccard-ish score weighted by overlap.
            score = overlap / max(len(query_tokens), len(clause_tokens))
            doc = docs.get(str(c.document_id))
            scored.append(
                {
                    "score": round(score, 3),
                    "clause_id": str(c.id),
                    "clause_ref": c.clause_ref,
                    "heading": c.heading,
                    "text": text[:300],
                    "page": c.page_from,
                    "document_id": str(c.document_id),
                    "filename": doc.filename if doc else None,
                    "document_kind": doc.kind if doc else None,
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def diff(self, workspace_id, opportunity_id, document_id: str | None = None) -> dict:
        svc = self._ingestion()
        if svc is None:
            return {"added": [], "removed": [], "changed": []}

        old_doc, new_doc = self._resolve_pair(svc, workspace_id, opportunity_id, document_id)
        if old_doc is None or new_doc is None:
            return {"added": [], "removed": [], "changed": []}

        old_clauses = svc.list_clauses_for_document(workspace_id, str(old_doc.id))
        new_clauses = svc.list_clauses_for_document(workspace_id, str(new_doc.id))

        old_by_ref = {c.clause_ref or f"__{i}": c for i, c in enumerate(old_clauses)}
        new_by_ref = {c.clause_ref or f"__{i}": c for i, c in enumerate(new_clauses)}

        added, removed, changed = [], [], []
        for ref, c in new_by_ref.items():
            old = old_by_ref.get(ref)
            if old is None:
                added.append(self._clause_json(c, new_doc))
            elif self._norm(old.text) != self._norm(c.text):
                changed.append(
                    {
                        "clause_ref": c.clause_ref,
                        "old": self._clause_json(old, old_doc),
                        "new": self._clause_json(c, new_doc),
                        "similarity": round(
                            difflib.SequenceMatcher(
                                None, self._norm(old.text), self._norm(c.text)
                            ).ratio(),
                            3,
                        ),
                    }
                )

        for ref, c in old_by_ref.items():
            if ref not in new_by_ref:
                removed.append(self._clause_json(c, old_doc))

        return {
            "old_document_id": str(old_doc.id),
            "new_document_id": str(new_doc.id),
            "added": added,
            "removed": removed,
            "changed": changed,
        }

    def _resolve_pair(self, svc, workspace_id, opportunity_id, document_id):
        if document_id:
            new_doc = svc.get_document(workspace_id, document_id)
            if new_doc is None or new_doc.supersedes is None:
                return None, None
            old_doc = svc.get_document(workspace_id, str(new_doc.supersedes))
            return old_doc, new_doc

        docs = svc.list_documents(workspace_id, opportunity_id)
        if not docs:
            return None, None
        # Group by kind and pick the most recent pair within each kind.
        by_kind: dict[str, list] = {}
        for d in docs:
            by_kind.setdefault(d.kind, []).append(d)
        for _kind, items in by_kind.items():
            if len(items) >= 2:
                items.sort(key=lambda d: (d.created_at, str(d.id)))
                return items[0], items[-1]
        # Otherwise try explicit supersedes chain across the whole opportunity.
        for d in sorted(docs, key=lambda d: (d.created_at, str(d.id))):
            if d.supersedes:
                old = svc.get_document(workspace_id, str(d.supersedes))
                if old:
                    return old, d
        return None, None

    @staticmethod
    def _norm(text: str | None) -> str:
        return re.sub(r"\s+", " ", (text or "").lower()).strip()

    @staticmethod
    def _clause_json(c, doc) -> dict:
        return {
            "clause_id": str(c.id),
            "clause_ref": c.clause_ref,
            "heading": c.heading,
            "text": c.text[:300],
            "page": c.page_from,
            "document_id": str(doc.id),
            "filename": doc.filename,
        }

    def _precedence(self, workspace_id, opportunity_id) -> tuple[str, ...]:
        """Rulepacks is a soft dependency: absent entirely, or shipping no
        document_precedence config, both degrade to DEFAULT_PRECEDENCE rather
        than crashing (CLAUDE.md §2)."""
        loader = self._rulepacks_loader() if self._rulepacks_loader else None
        if loader is None:
            return DEFAULT_PRECEDENCE
        employer_family = None
        svc = self._ingestion()
        if svc is not None:
            opp = svc.get_opportunity(workspace_id, opportunity_id)
            employer_family = opp.employer_family if opp else None
        order = loader.document_precedence(
            self._pack_id,
            employer_family,
            session=self.s,
            workspace_id=workspace_id,
        )
        return tuple(order) if order else DEFAULT_PRECEDENCE

    def contradictions(self, workspace_id, opportunity_id) -> dict:
        """Fact-level cross-document contradiction detection (TS-217,
        Strategy §C.5): validity/EMD/submission-datetime/LD-rate/DLP/retention
        facts, deterministically extracted per clause, grouped by type, with
        the document-precedence order naming the governing instance when they
        disagree."""
        svc = self._ingestion()
        if svc is None:
            return {"contradictions": []}

        docs = {str(d.id): d for d in svc.list_documents(workspace_id, opportunity_id)}
        clauses = [
            {
                "id": str(c.id),
                "document_id": str(c.document_id),
                "document_kind": docs[str(c.document_id)].kind
                if str(c.document_id) in docs
                else "other",
                "text": c.text,
                "page_from": c.page_from,
            }
            for c in svc.list_clauses(workspace_id, opportunity_id)
        ]
        precedence = self._precedence(workspace_id, opportunity_id)
        found = find_contradictions(clauses, precedence=precedence)
        return {
            "precedence": list(precedence),
            "contradictions": [self._contradiction_json(c, docs) for c in found],
        }

    @staticmethod
    def _contradiction_json(c: Contradiction, docs: dict) -> dict:
        def instance_json(f: CanonicalFact) -> dict:
            doc = docs.get(f.document_id)
            return {
                "value": f.value,
                "unit": f.unit,
                "document_id": f.document_id,
                "document_kind": f.document_kind,
                "filename": doc.filename if doc else None,
                "clause_id": f.clause_id,
                "page": f.source_page,
                "quote": f.source_quote,
            }

        return {
            "fact_type": c.fact_type,
            "instances": [instance_json(f) for f in c.instances],
            "governing": instance_json(c.governing) if c.governing else None,
            "governing_reason": c.governing_reason,
        }
