"""Award-vs-tender comparison helpers (TS-236).

Deterministic diffs for findings, segmented clauses, and BOQ-related findings.
No LLM — every quote is a verbatim substring of source text.
"""

from __future__ import annotations

import hashlib
import re

_BOQ_KINDS = frozenset({"boq_defect"})


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _clause_key(clause: dict) -> str:
    ref = clause.get("clause_ref") or clause.get("title")
    if ref:
        return f"ref:{ref}"
    digest = hashlib.sha256(_norm(clause.get("text", "")).encode()).hexdigest()[:16]
    return f"text:{digest}"


def _quote_slice(text: str, *, limit: int = 200) -> str:
    return (text or "")[:limit]


def diff_clauses(tender_clauses: list[dict], award_clauses: list[dict]) -> dict:
    tender_index = {_clause_key(c): c for c in tender_clauses}
    award_index = {_clause_key(c): c for c in award_clauses}

    added: list[dict] = []
    removed: list[dict] = []
    changed: list[dict] = []

    for key, award_clause in award_index.items():
        if key not in tender_index:
            added.append(
                {
                    "clause_ref": award_clause.get("clause_ref"),
                    "source_page": award_clause.get("page_from"),
                    "source_quote": _quote_slice(award_clause.get("text", "")),
                }
            )
            continue
        tender_clause = tender_index[key]
        if _norm(tender_clause.get("text", "")) != _norm(award_clause.get("text", "")):
            changed.append(
                {
                    "clause_ref": award_clause.get("clause_ref"),
                    "source_page": award_clause.get("page_from"),
                    "tender_quote": _quote_slice(tender_clause.get("text", "")),
                    "award_quote": _quote_slice(award_clause.get("text", "")),
                }
            )

    for key, tender_clause in tender_index.items():
        if key not in award_index:
            removed.append(
                {
                    "clause_ref": tender_clause.get("clause_ref"),
                    "source_page": tender_clause.get("page_from"),
                    "source_quote": _quote_slice(tender_clause.get("text", "")),
                }
            )

    return {"added": added, "removed": removed, "changed": changed}


def _finding_identity(finding: dict) -> tuple[str, str]:
    return (finding.get("category", ""), finding.get("title", ""))


def diff_findings(tender_findings: list[dict], award_findings: list[dict]) -> dict:
    tender = {_finding_identity(f): f for f in tender_findings}
    award = {_finding_identity(f): f for f in award_findings}

    added = [award[k] for k in award.keys() - tender.keys()]
    removed = [tender[k] for k in tender.keys() - award.keys()]
    changed: list[dict] = []
    for key in tender.keys() & award.keys():
        tf, af = tender[key], award[key]
        diffs = {
            field: {"tender": tf.get(field), "award": af.get(field)}
            for field in ("severity", "detail", "amount_exposure", "source_quote")
            if tf.get(field) != af.get(field)
        }
        if diffs:
            changed.append({"category": key[0], "title": key[1], "changes": diffs})

    return {"added": added, "removed": removed, "changed": changed}


def _boq_findings(findings: list[dict]) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for row in findings:
        if row.get("kind") in _BOQ_KINDS or row.get("category") in {"arith", "duplicate"}:
            out[_finding_identity(row)] = row
    return out


def diff_boq(tender_findings: list[dict], award_findings: list[dict]) -> list[dict]:
    tender = _boq_findings(tender_findings)
    award = _boq_findings(award_findings)
    deltas: list[dict] = []
    for key in tender.keys() | award.keys():
        tf = tender.get(key)
        af = award.get(key)
        if tf is None:
            deltas.append({"change": "added", "category": key[0], "title": key[1], "award": af})
        elif af is None:
            deltas.append({"change": "removed", "category": key[0], "title": key[1], "tender": tf})
        elif tf.get("detail") != af.get("detail") or tf.get("amount_exposure") != af.get(
            "amount_exposure"
        ):
            deltas.append(
                {
                    "change": "modified",
                    "category": key[0],
                    "title": key[1],
                    "tender": {
                        "detail": tf.get("detail"),
                        "amount_exposure": tf.get("amount_exposure"),
                        "source_quote": tf.get("source_quote"),
                    },
                    "award": {
                        "detail": af.get("detail"),
                        "amount_exposure": af.get("amount_exposure"),
                        "source_quote": af.get("source_quote"),
                    },
                }
            )
    return deltas
