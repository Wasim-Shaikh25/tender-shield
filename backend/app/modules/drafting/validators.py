"""The three artifact validators — the product's spine (Doc §6.5):
no invented quotes, no uncited clauses, no invented numbers. Pure and
exhaustively testable; they gate every generated artifact, whether the prose
was assembled deterministically or written by an LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


class DraftError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


_QUOTE_RE = re.compile(r"[\"“]([^\"”]{6,})[\"”]")
_CLAUSE_RE = re.compile(r"(?:Clause|GCC|SCC)\s+\d+[A-Za-z]?(?:\.\d+)*(?:\([ivxlcdm0-9a-z]+\))?")
_AMOUNT_RE = re.compile(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


@dataclass
class FactTable:
    """The ONLY sanctioned source of quotes/clause-refs/amounts for an artifact,
    built from accepted findings."""

    quotes: list[str] = field(default_factory=list)
    clause_refs: set[str] = field(default_factory=set)
    amounts: list[float] = field(default_factory=list)

    @classmethod
    def from_findings(cls, findings) -> FactTable:
        quotes, refs, amounts = [], set(), []
        for f in findings:
            grounded = " ".join(filter(None, [f.get("source_quote"), f.get("detail")]))
            if f.get("source_quote"):
                quotes.append(_norm(f["source_quote"]))
            for m in _CLAUSE_RE.finditer(grounded):
                refs.add(m.group(0))
            if f.get("amount_exposure") is not None:
                amounts.append(float(f["amount_exposure"]))
            for m in _AMOUNT_RE.finditer(grounded):
                value = float(m.group(1).replace(",", ""))
                if value not in amounts:
                    amounts.append(value)
        return cls(quotes=quotes, clause_refs=refs, amounts=amounts)

    def has_quote(self, q: str) -> bool:
        nq = _norm(q)
        return any(nq in fq or fq in nq for fq in self.quotes)

    def has_amount(self, value: float, tol: float = 0.5) -> bool:
        return any(abs(value - a) <= tol for a in self.amounts)


def validate(prose: str, facts: FactTable) -> str:
    """Raise DraftError on any invented quote / uncited clause / invented number.
    Returns the prose unchanged on success."""
    for m in _QUOTE_RE.finditer(prose):
        if not facts.has_quote(m.group(1)):
            raise DraftError("invented_quote", m.group(1)[:60])
    for m in _CLAUSE_RE.finditer(prose):
        if m.group(0) not in facts.clause_refs:
            raise DraftError("uncited_clause", m.group(0))
    for m in _AMOUNT_RE.finditer(prose):
        value = float(m.group(1).replace(",", ""))
        if not facts.has_amount(value):
            raise DraftError("invented_number", m.group(1))
    return prose
