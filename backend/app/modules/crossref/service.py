"""CrossRefService — search clauses across documents and diff document versions.

Consumes ingestion via registry; no imports of other modules (CLAUDE.md §2)."""

from __future__ import annotations

import difflib
import re


class CrossRefService:
    def __init__(self, session, *, ingestion_factory=None):
        self.s = session
        self._ingestion_factory = ingestion_factory

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
