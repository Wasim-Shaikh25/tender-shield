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
