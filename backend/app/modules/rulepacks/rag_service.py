"""RAG-assisted rulepack expansion (TS-351).

Source circulars / rulebooks are parsed by the ingestion text extractor and
passed to an LLM with the current pack payload. The LLM returns *suggested*
rulepack fragments (patterns, notice standards, trade checklists, etc.). Each
suggestion is stored in `rp_rag_suggestions` and must be human-approved before
it becomes a new draft RulePack version — the deterministic YAML rulepack stays
the source of truth.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import re
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage import StorageBackend
from app.modules.rulepacks.admin_service import bump_version
from app.modules.rulepacks.models import RagSuggestion, RulePack, RulePackFile

logger = logging.getLogger(__name__)

_ALLOWED_KINDS = {
    "patterns",
    "doc_types",
    "expected_documents",
    "unit_canon",
    "boq_checks",
    "trade_checklists",
    "playbooks",
    "notice_standards",
    "rate_schedules",
    "document_precedence",
    "employer_families",
    "meta",
}

_LIST_KINDS = {"expected_documents"}


class RagSuggestionError(Exception):
    def __init__(self, code: str, details: dict | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(code)


def _to_uuid(value) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


class RagSuggestionService:
    def __init__(
        self,
        session: Session,
        *,
        settings,
        storage: StorageBackend,
        ingestion_factory: Callable | None = None,
        llm_client: Any | None = None,
        publish: Callable[[str, dict], int] | None = None,
    ) -> None:
        self.s = session
        self._settings = settings
        self._storage = storage
        self._ingestion_factory = ingestion_factory
        self._llm_client = llm_client
        self._publish = publish

    def _read_file(self, storage_key: str) -> bytes:
        """Sync wrapper for the async storage backend read."""

        async def _read() -> bytes:
            return await self._storage.read(storage_key)

        try:
            return asyncio.run(_read())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_read())
            finally:
                loop.close()

    def _extract_text(self, filename: str, data: bytes) -> str:
        if self._ingestion_factory is None:
            raise RagSuggestionError("ingestion_unavailable")
        ing = self._ingestion_factory(self.s)
        if not hasattr(ing, "extract_text"):
            raise RagSuggestionError("ingestion_unavailable")
        return ing.extract_text(filename, data)

    def _get_llm_client(self):
        if self._llm_client is not None:
            return self._llm_client
        from app.core.llm import openrouter_client

        return openrouter_client("rulepacks.rag")

    def _build_prompt(self, pack_payload: dict, text: str) -> str:
        summary = {
            "meta": pack_payload.get("meta", {}),
            "patterns": list(pack_payload.get("patterns", {}).keys()),
            "notice_standards": list(pack_payload.get("notice_standards", {}).keys()),
            "trade_checklists": list(pack_payload.get("trade_checklists", {}).keys()),
            "doc_types": list(pack_payload.get("doc_types", {}).keys()),
        }
        text_sample = text[:20000]
        return (
            "You are a tender-rulepack assistant. Given an existing rulepack summary and the "
            "extracted text of a source circular/rulebook, propose new rulepack YAML fragments. "
            "Return ONLY a JSON array. Each element must have:\n"
            "  kind: one of patterns, doc_types, expected_documents, unit_canon, boq_checks, "
            "        trade_checklists, playbooks, notice_standards, rate_schedules, "
            "        document_precedence, employer_families, meta\n"
            "  proposed_yaml: a YAML-compatible JSON object that can be merged into the existing "
            "        rulepack under that kind\n"
            "  rationale: why the addition is needed\n"
            "  source_quote: the exact short verbatim quote from the circular that supports it\n"
            "  source_page: page number if known, else null\n"
            "  confidence: 'unvalidated'\n"
            "\nFor dict-valued kinds (patterns, doc_types, trade_checklists, notice_standards, "
            "rate_schedules, playbooks, unit_canon, employer_families, document_precedence, "
            "boq_checks, meta), proposed_yaml is a single-key object whose key is the id/scope "
            "and value is the full object. For list-valued kinds (expected_documents), "
            "proposed_yaml is a list of strings.\n"
            "\nExisting rulepack summary:\n"
            f"{json.dumps(summary, indent=2)}\n"
            "\nSource circular text:\n"
            f"{text_sample}\n"
            "\nReturn ONLY the JSON array, no markdown, no commentary."
        )

    def _parse_suggestions(self, raw: str) -> list[dict]:
        raw = raw.strip()
        if raw.startswith("```"):
            m = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
            if m:
                raw = m.group(1)
        if not raw.startswith("["):
            start = raw.find("[")
            end = raw.rfind("]")
            if start != -1 and end != -1:
                raw = raw[start : end + 1]
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RagSuggestionError("invalid_llm_response", {"detail": str(exc)}) from exc

    def suggest_from_file(
        self,
        rulepack_id: uuid.UUID | str,
        file_id: uuid.UUID | str,
        workspace_id: uuid.UUID | str | None,
        user_id: uuid.UUID | str,
    ) -> Sequence[dict]:
        rp_uuid = _to_uuid(rulepack_id)
        file_uuid = _to_uuid(file_id)
        ws_uuid = _to_uuid(workspace_id) if workspace_id else None

        pack = self.s.execute(select(RulePack).where(RulePack.id == rp_uuid)).scalars().first()
        if pack is None:
            raise RagSuggestionError("rulepack_not_found")
        if pack.scope == "workspace" and pack.workspace_id != ws_uuid:
            raise RagSuggestionError("forbidden_rulepack")

        file_row = self.s.execute(
            select(RulePackFile).where(
                RulePackFile.id == file_uuid, RulePackFile.rulepack_id == rp_uuid
            )
        ).scalars().first()
        if file_row is None:
            raise RagSuggestionError("source_file_not_found")

        data = self._read_file(file_row.storage_key)
        text = self._extract_text(file_row.path, data)
        if not text.strip():
            raise RagSuggestionError("no_extractable_text")

        client = self._get_llm_client()
        if client is None:
            raise RagSuggestionError("llm_unavailable")

        prompt = self._build_prompt(pack.payload or {}, text)
        try:
            response = client.chat.completions.create(
                model=self._settings.openrouter_model,
                max_tokens=2000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.choices[0].message.content or "[]"
        except Exception as exc:
            logger.exception("RAG suggestion LLM call failed")
            raise RagSuggestionError("llm_failed", {"detail": str(exc)}) from exc

        items = self._parse_suggestions(raw)
        created = []
        for item in items:
            kind = str(item.get("kind", ""))
            if kind not in _ALLOWED_KINDS:
                continue
            row = RagSuggestion(
                id=uuid.uuid4(),
                workspace_id=ws_uuid,
                rulepack_id=pack.id,
                source_file_id=file_row.id,
                kind=kind,
                proposed_yaml=item.get("proposed_yaml", {}),
                rationale=str(item.get("rationale", ""))[:1000],
                source_quote=str(item.get("source_quote", ""))[:1000],
                source_page=item.get("source_page"),
                confidence=str(item.get("confidence", "unvalidated")),
                status="proposed",
            )
            self.s.add(row)
            created.append(row)
        self.s.commit()

        if self._publish:
            self._publish(
                "rulepack.rag_suggestions_created",
                {
                    "rulepack_id": str(pack.id),
                    "workspace_id": str(ws_uuid) if ws_uuid else None,
                    "count": len(created),
                },
            )

        return [self._to_summary(r) for r in created]

    def list_suggestions(
        self,
        rulepack_id: uuid.UUID | str,
        workspace_id: uuid.UUID | str | None,
        *,
        status: str | None = None,
    ) -> Sequence[dict]:
        ws_uuid = _to_uuid(workspace_id) if workspace_id else None
        q = select(RagSuggestion).where(
            RagSuggestion.rulepack_id == _to_uuid(rulepack_id),
            RagSuggestion.workspace_id == ws_uuid,
        )
        if status:
            q = q.where(RagSuggestion.status == status)
        rows = self.s.execute(q.order_by(RagSuggestion.created_at.desc())).scalars().all()
        return [self._to_summary(r) for r in rows]

    def approve_suggestion(
        self,
        suggestion_id: uuid.UUID | str,
        workspace_id: uuid.UUID | str | None,
        user_id: uuid.UUID | str,
    ) -> dict:
        ws_uuid = _to_uuid(workspace_id) if workspace_id else None
        row = self.s.execute(
            select(RagSuggestion).where(
                RagSuggestion.id == _to_uuid(suggestion_id),
                RagSuggestion.workspace_id == ws_uuid,
            )
        ).scalars().first()
        if row is None:
            raise RagSuggestionError("suggestion_not_found")
        if row.status != "proposed":
            raise RagSuggestionError("already_reviewed")

        pack = self.s.execute(
            select(RulePack).where(RulePack.id == row.rulepack_id)
        ).scalars().first()
        if pack is None:
            raise RagSuggestionError("rulepack_not_found")

        new_version = bump_version(
            self.s, pack.pack_id, pack.version, pack.scope, pack.workspace_id
        )
        if new_version == pack.version:
            new_version = f"{pack.version}-rag"
            new_version = bump_version(
                self.s, pack.pack_id, new_version, pack.scope, pack.workspace_id
            )

        new_payload = copy.deepcopy(pack.payload or {})
        new_payload = self._merge_fragment(new_payload, row.kind, row.proposed_yaml)
        new_meta = copy.deepcopy(pack.meta or {})
        sources = new_meta.get("sources", [])
        if isinstance(sources, list):
            sources.append(f"RAG suggestion {row.id} from file {row.source_file_id}")
            new_meta["sources"] = sources
        new_meta["version"] = new_version

        new_pack = RulePack(
            id=uuid.uuid4(),
            pack_id=pack.pack_id,
            version=new_version,
            scope=pack.scope,
            workspace_id=pack.workspace_id,
            jurisdiction=pack.jurisdiction,
            is_active=False,
            status="draft",
            meta=new_meta,
            payload=new_payload,
            uploaded_by=_to_uuid(user_id),
        )
        self.s.add(new_pack)

        row.status = "approved"
        row.reviewed_at = datetime.now(UTC)
        row.reviewed_by = _to_uuid(user_id)
        self.s.commit()

        if self._publish:
            self._publish(
                "rulepack.rag_suggestion_approved",
                {
                    "rulepack_id": str(pack.id),
                    "new_rulepack_id": str(new_pack.id),
                    "workspace_id": str(ws_uuid) if ws_uuid else None,
                },
            )

        return {
            "suggestion_id": str(row.id),
            "new_rulepack": {
                "id": str(new_pack.id),
                "pack_id": new_pack.pack_id,
                "version": new_pack.version,
                "scope": new_pack.scope,
                "status": new_pack.status,
                "is_active": new_pack.is_active,
            },
        }

    def reject_suggestion(
        self,
        suggestion_id: uuid.UUID | str,
        workspace_id: uuid.UUID | str | None,
        user_id: uuid.UUID | str,
    ) -> dict:
        ws_uuid = _to_uuid(workspace_id) if workspace_id else None
        row = self.s.execute(
            select(RagSuggestion).where(
                RagSuggestion.id == _to_uuid(suggestion_id),
                RagSuggestion.workspace_id == ws_uuid,
            )
        ).scalars().first()
        if row is None:
            raise RagSuggestionError("suggestion_not_found")
        if row.status != "proposed":
            raise RagSuggestionError("already_reviewed")
        row.status = "rejected"
        row.reviewed_at = datetime.now(UTC)
        row.reviewed_by = _to_uuid(user_id)
        self.s.commit()
        return {"id": str(row.id), "status": row.status}

    def _merge_fragment(self, payload: dict, kind: str, fragment: Any) -> dict:
        if kind == "meta":
            if isinstance(fragment, dict):
                payload["meta"] = {**(payload.get("meta") or {}), **fragment}
            return payload

        if kind in _LIST_KINDS:
            payload.setdefault(kind, [])
            existing = set(payload[kind])
            for item in fragment:
                if item not in existing:
                    payload[kind].append(item)
            return payload

        payload.setdefault(kind, {})
        if isinstance(fragment, dict) and isinstance(payload[kind], dict):
            for key, value in fragment.items():
                if kind == "notice_standards" and key in payload[kind] and isinstance(value, dict):
                    base = payload[kind][key]
                    if isinstance(base, dict):
                        merged = {**base, **value}
                        if "categories" in base and "categories" in value:
                            base_cats = {
                                c["key"]: c
                                for c in base.get("categories", [])
                                if isinstance(c, dict)
                            }
                            for cat in value.get("categories", []):
                                if isinstance(cat, dict) and "key" in cat:
                                    prev = base_cats.get(cat["key"], {})
                                    base_cats[cat["key"]] = {**prev, **cat}
                            merged["categories"] = list(base_cats.values())
                        payload[kind][key] = merged
                        continue
                payload[kind][key] = value
        else:
            payload[kind] = fragment
        return payload

    def _to_summary(self, row: RagSuggestion) -> dict:
        return {
            "id": str(row.id),
            "rulepack_id": str(row.rulepack_id),
            "source_file_id": str(row.source_file_id) if row.source_file_id else None,
            "kind": row.kind,
            "proposed_yaml": row.proposed_yaml,
            "rationale": row.rationale,
            "source_quote": row.source_quote,
            "source_page": row.source_page,
            "confidence": row.confidence,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        }
