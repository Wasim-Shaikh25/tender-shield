"""Risk-pattern engine (Doc §6.3): retrieve candidate clauses → LLM classifies
→ deterministic severity + quote verification. The engine is pure over plain
dicts; the classifier is injected (Protocol) so it can be faked in tests and
swapped without touching the engine."""

from __future__ import annotations

import difflib
import re
from typing import Protocol

from app.core.contracts.findings import Finding, FindingKind, FindingSource, Severity
from app.modules.risk.severity import evaluate_severity

# A candidate/clause is a plain dict: {id, clause_ref, text, page_from}
Clause = dict


class Classifier(Protocol):
    def classify(self, pattern, candidates: list[Clause]) -> list[dict]:
        """Return per-finding dicts: {found, finding, facts, source_quote,
        source_page}. Never fabricates severity (that is computed here)."""
        ...


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def retrieve_candidates(
    clauses: list[Clause], anchor_queries: list[str], k: int = 12
) -> list[Clause]:
    anchors = [a.lower() for a in anchor_queries]
    hits = [c for c in clauses if any(a in _norm(c.get("text", "")) for a in anchors)]
    return hits[:k]


def verify_quote(quote: str, candidates: list[Clause], threshold: float = 0.85) -> bool:
    if not quote:
        return False
    nq = _norm(quote)
    for c in candidates:
        text = _norm(c.get("text", ""))
        if nq in text:
            return True
        if difflib.SequenceMatcher(None, nq, text).ratio() >= threshold:
            return True
        # also try the best-matching window of the clause
        if len(nq) < len(text):
            for i in range(0, len(text) - len(nq) + 1, max(1, len(nq) // 2)):
                window = text[i : i + len(nq)]
                if difflib.SequenceMatcher(None, nq, window).ratio() >= threshold:
                    return True
    return False


def _build_explanation(pattern, quote: str | None, *, absence: bool = False) -> dict:
    return {
        "matched_pattern": {"id": pattern.id, "title": pattern.title, "category": pattern.category},
        "evidence_quote": quote,
        "industry_reason": pattern.industry_reason or "Pattern matched the contract text.",
        "suggested_review": pattern.suggested_clarification or "Review with the commercial team.",
        "absence": absence,
    }


def _pattern_disclaimer(pattern, disclaimer: str | None) -> str | None:
    return disclaimer if getattr(pattern, "confidence", None) == "unvalidated" else None


def _absence_finding(pattern, opp_facts: dict, disclaimer: str | None = None) -> Finding:
    return Finding(
        kind=FindingKind.RISK_CLAUSE,
        category=pattern.category,
        severity=Severity(evaluate_severity(pattern.severity_rule, opp_facts)),
        title=f"{pattern.title} — clause appears ABSENT",
        detail=(
            f"No clause matching pattern '{pattern.id}' was found. Absence itself "
            "is the finding (Doc §6.3); confirm the omission independently."
        ),
        source=FindingSource.AI_SUGGESTION,
        suggested_action=pattern.suggested_clarification,
        affected_trades=list(pattern.affected_trades),
        pattern_id=pattern.id,
        explanation=_build_explanation(pattern, None, absence=True),
        disclaimer=_pattern_disclaimer(pattern, disclaimer),
    )


def run_pattern(
    pattern,
    clauses: list[Clause],
    classifier: Classifier,
    opp_facts: dict | None = None,
    disclaimer: str | None = None,
) -> list[Finding]:
    opp_facts = opp_facts or {}
    candidates = retrieve_candidates(clauses, list(pattern.anchor_queries))
    if not candidates:
        return (
            [_absence_finding(pattern, opp_facts, disclaimer=disclaimer)]
            if pattern.absence_is_finding
            else []
        )

    findings: list[Finding] = []
    for result in classifier.classify(pattern, candidates):
        if not result.get("found"):
            continue
        ctx = {**opp_facts, **result.get("facts", {})}
        severity = Severity(evaluate_severity(pattern.severity_rule, ctx))
        quote = result.get("source_quote", "") or ""
        verified = verify_quote(quote, candidates)
        detail = result.get("finding", "")
        if quote and not verified:
            detail += "  [unverified quote — confidence low, confirm in source]"
        findings.append(
            Finding(
                kind=FindingKind.RISK_CLAUSE,
                category=pattern.category,
                severity=severity,
                title=pattern.title,
                detail=detail,
                source=FindingSource.AI_SUGGESTION,
                source_page=result.get("source_page"),
                source_quote=quote[:200] if verified else None,
                suggested_action=pattern.suggested_clarification,
                affected_trades=list(pattern.affected_trades),
                pattern_id=pattern.id,
                explanation=_build_explanation(pattern, quote[:200] if verified else quote),
                disclaimer=_pattern_disclaimer(pattern, disclaimer),
            )
        )
    return findings


def run_patterns(
    patterns,
    clauses: list[Clause],
    classifier: Classifier,
    opp_facts: dict | None = None,
    disclaimer: str | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    for pattern in patterns:
        findings.extend(run_pattern(pattern, clauses, classifier, opp_facts, disclaimer=disclaimer))
    return findings
