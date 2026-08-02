"""Normalize clause shapes and build diff candidates (TS-245).

Pure helpers — no cross-module imports. Diff functions are injected via the
registry (`baseline.diff_clauses`).
"""

from __future__ import annotations

import hashlib


def normalize_clause(clause: dict) -> dict:
    """Map baseline snapshot or segment clauses to a common diff shape."""
    if clause.get("text"):
        return {
            "clause_ref": clause.get("clause_ref") or clause.get("title"),
            "text": clause.get("text", ""),
            "page_from": clause.get("page_from") or clause.get("source_page"),
        }
    return {
        "clause_ref": clause.get("title") if clause.get("title") != "clause" else None,
        "text": clause.get("detail") or clause.get("source_quote") or "",
        "page_from": clause.get("source_page"),
    }


def _value(seg, key: str, default=None):
    if isinstance(seg, dict):
        return seg.get(key, default)
    return getattr(seg, key, default)


def clauses_from_segments(segments) -> list[dict]:
    return [
        {
            "clause_ref": _value(seg, "clause_ref"),
            "text": _value(seg, "text", ""),
            "page_from": _value(seg, "page_from"),
        }
        for seg in segments
    ]


def content_hash(*parts: str) -> str:
    joined = "|".join(p for p in parts if p)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def candidates_from_diff(
    diff: dict,
    *,
    document_id: str | None = None,
    reason: str = "spec_revision",
) -> list[dict]:
    """Turn clause diff output into candidate event payloads."""
    out: list[dict] = []
    for item in diff.get("added", []):
        quote = item.get("source_quote") or ""
        ref = item.get("clause_ref") or "new clause"
        out.append(
            {
                "title": f"New clause: {ref}",
                "reason": reason,
                "confidence_band": "high" if quote else "medium",
                "notice_type": "variation",
                "source_kind": "baseline_diff",
                "document_id": document_id,
                "source_page": item.get("source_page"),
                "source_quote": quote,
                "sha256": content_hash("added", ref, quote),
            }
        )
    for item in diff.get("changed", []):
        quote = item.get("award_quote") or item.get("source_quote") or ""
        ref = item.get("clause_ref") or "clause"
        out.append(
            {
                "title": f"Revised clause: {ref}",
                "reason": reason,
                "confidence_band": "high" if quote else "medium",
                "notice_type": "variation",
                "source_kind": "baseline_diff",
                "document_id": document_id,
                "source_page": item.get("source_page"),
                "source_quote": quote,
                "sha256": content_hash("changed", ref, quote),
            }
        )
    return out
