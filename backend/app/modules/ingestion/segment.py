"""Clause segmentation (Doc §3.2 `clauses`) — pure, deterministic, no I/O.

Digital-text heuristic: split on clause headers (Clause/GCC/SCC N[.n]) and
track page from [pN] markers. Scanned-PDF segmentation hardening is later work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_PAGE = re.compile(r"^\s*\[p(\d+)\]\s*$")
_REF = r"\d+[A-Za-z]?(?:\.\d+)*(?:\([ivxlcdm0-9a-z]+\))?"
_HEADER = re.compile(
    rf"^\s*(?P<kind>Clause|GCC|SCC)\s+(?P<ref>{_REF})\s*[—\-:.]?\s*(?P<heading>.*)$"
)
_XREF = re.compile(rf"(?:Clause|GCC|SCC)\s+{_REF}")


@dataclass
class ClauseSeg:
    clause_ref: str | None
    heading: str | None
    text: str
    page_from: int
    page_to: int
    cross_refs: list[str] = field(default_factory=list)


def _finalize(seg: ClauseSeg) -> ClauseSeg:
    seg.text = seg.text.strip()
    refs = {m.group(0).strip() for m in _XREF.finditer(seg.text)}
    # drop the clause's own self-reference (e.g. "Clause 33" inside clause 33)
    self_ref = None
    if seg.clause_ref:
        self_ref = {f"Clause {seg.clause_ref}", f"GCC {seg.clause_ref}", f"SCC {seg.clause_ref}"}
    seg.cross_refs = sorted(r for r in refs if not self_ref or r not in self_ref)
    return seg


def segment_clauses(text: str) -> list[ClauseSeg]:
    segments: list[ClauseSeg] = []
    current: ClauseSeg | None = None
    page = 1
    for line in text.splitlines():
        pm = _PAGE.match(line)
        if pm:
            page = int(pm.group(1))
            continue
        hm = _HEADER.match(line)
        if hm:
            if current is not None:
                segments.append(_finalize(current))
            current = ClauseSeg(
                clause_ref=hm.group("ref"),
                heading=hm.group("heading").strip() or None,
                text=line,
                page_from=page,
                page_to=page,
            )
        elif current is not None:
            current.text += "\n" + line
            current.page_to = page
        else:
            # preamble before the first clause header (e.g. the NIT block)
            current = ClauseSeg(
                clause_ref=None, heading="Preamble", text=line, page_from=page, page_to=page
            )
    if current is not None:
        segments.append(_finalize(current))
    return [s for s in segments if s.text]


@dataclass(frozen=True)
class DefinedTermSeg:
    term: str
    definition: str
    source_quote: str
    source_clause_ref: str | None


# Patterns that capture "X means Y" / "X shall mean Y" / "X is defined as" definitions.
_QUOTED_TERM = r'[“""]([^"]+)["""]?\s+means\s+"?(.+?)"?\s*[.;]\s*$'
_CAPITAL_TERM = r'\b([A-Z][A-Za-z0-9\s]{1,50})\s+'
_DEFINITION_PATTERNS = [
    re.compile(_QUOTED_TERM, re.IGNORECASE | re.MULTILINE),
    re.compile(_CAPITAL_TERM + r'means\s+(.+?)[.;]\s*$', re.IGNORECASE | re.MULTILINE),
    re.compile(_CAPITAL_TERM + r'shall\s+mean\s+(.+?)[.;]\s*$', re.IGNORECASE | re.MULTILINE),
    re.compile(
        _CAPITAL_TERM + r'shall\s+be\s+defined\s+as\s+(.+?)[.;]\s*$',
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        _CAPITAL_TERM + r'is\s+defined\s+as\s+(.+?)[.;]\s*$',
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r'(?:the\s+)?"([A-Z][A-Za-z0-9\s]{1,50})"\s+(?:means|is\s+defined\s+as)\s+(.+?)[.;]\s*$',
        re.IGNORECASE | re.MULTILINE,
    ),
]


def segment_defined_terms(text: str) -> list[DefinedTermSeg]:
    """Extract 'X means Y' style definitions from a tender document.

    Returns terms with the original sentence as the source quote. This is
    intentionally conservative: it avoids false positives by requiring a capitalised
    term and a definition verb (means / shall mean / is defined as).
    """
    terms: list[DefinedTermSeg] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) > 800:
            continue
        for pat in _DEFINITION_PATTERNS:
            for match in pat.finditer(line):
                term = match.group(1).strip()
                definition = match.group(2).strip()
                if not term or not definition or len(term) < 2:
                    continue
                if term.lower() in ("this", "that", "the", "a", "an"):
                    continue
                key = f"{term.lower()}:{definition.lower()[:80]}"
                if key in seen:
                    continue
                seen.add(key)
                terms.append(
                    DefinedTermSeg(
                        term=term,
                        definition=definition,
                        source_quote=line,
                        source_clause_ref=None,
                    )
                )
    return terms
