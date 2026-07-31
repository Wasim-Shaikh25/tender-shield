"""Fact-level cross-document contradiction detection (Strategy Doc §C.5,
TS-217).

Facts are regex-extracted per clause (facts.py), grouped by canonical type,
and — when a type disagrees across documents — a document-precedence order
(rulepack-configurable, employer-family overridable; see
`rulepacks/in-works/document_precedence.yaml`) names the *governing* instance.
Both sides of a contradiction keep their own citation; an instance whose
quote cannot be re-verified against its own clause text is dropped before
grouping, never surfaced (Strategy §C.5 — avoids false positives from
extraction noise)."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.crossref.facts import CanonicalFact, extract_facts

# Fallback used when no rulepack (or no document_precedence config) is
# available — soft-dependency degradation, never a crash (CLAUDE.md §2).
DEFAULT_PRECEDENCE: tuple[str, ...] = ("addendum", "scc", "gcc", "nit")


@dataclass(frozen=True)
class Contradiction:
    fact_type: str
    instances: tuple[CanonicalFact, ...]
    governing: CanonicalFact | None
    governing_reason: str


def _verify(fact: CanonicalFact, clause_text_by_id: dict[str, str]) -> bool:
    quote = fact.source_quote
    if not quote:
        return False
    return quote in clause_text_by_id.get(fact.clause_id, "")


def _rank(document_kind: str, precedence: tuple[str, ...]) -> int:
    try:
        return precedence.index(document_kind)
    except ValueError:
        return len(precedence)  # unknown kind ranks least-authoritative


def resolve_governing(
    instances: tuple[CanonicalFact, ...], precedence: tuple[str, ...]
) -> tuple[CanonicalFact | None, str]:
    ranked = sorted(instances, key=lambda f: _rank(f.document_kind, precedence))
    best_rank = _rank(ranked[0].document_kind, precedence)
    tied = [f for f in ranked if _rank(f.document_kind, precedence) == best_rank]
    if len(tied) > 1:
        return None, (
            f"ambiguous: {len(tied)} instances tie at the top precedence rank "
            f"(document kind {ranked[0].document_kind!r})"
        )
    return ranked[0], f"document kind {ranked[0].document_kind!r} outranks the other instance(s)"


def find_contradictions(
    clauses: list[dict],
    *,
    precedence: tuple[str, ...] = DEFAULT_PRECEDENCE,
) -> list[Contradiction]:
    """`clauses` are plain dicts: {id, document_id, document_kind, text, page_from}."""
    facts = extract_facts(clauses)
    text_by_clause = {str(c["id"]): (c.get("text") or "") for c in clauses}
    verified = [f for f in facts if _verify(f, text_by_clause)]

    by_type: dict[str, list[CanonicalFact]] = {}
    for f in verified:
        by_type.setdefault(f.fact_type, []).append(f)

    contradictions: list[Contradiction] = []
    for fact_type, instances in by_type.items():
        if len({f.value for f in instances}) < 2:
            continue  # every verified instance agrees — not a contradiction
        governing, reason = resolve_governing(tuple(instances), precedence)
        contradictions.append(
            Contradiction(
                fact_type=fact_type,
                instances=tuple(instances),
                governing=governing,
                governing_reason=reason,
            )
        )
    return contradictions
