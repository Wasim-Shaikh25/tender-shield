"""Deadline extraction (Doc §6.2) — deterministic date parsing from digital
text. Dates are never invented: each extracted deadline carries the verbatim
source line and page. The LLM (later) only helps on messy/relative cases; the
deterministic pass already handles the common explicit-date forms, so the
<3-minute deadline wall works with no API key."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

_PAGE = re.compile(r"^\s*\[p(\d+)\]\s*$")

# Explicit date forms common in Indian tenders.
_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
    "|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)
_DATE_RE = re.compile(
    rf"""(
        \d{{1,2}}[/\-.]\d{{1,2}}[/\-.]\d{{4}}      # 25/07/2026, 25-07-2026, 25.07.2026
        | \d{{1,2}}\s+(?:{_MONTHS})\s+\d{{4}}       # 25 August 2026 / 25 Aug 2026
        | (?:{_MONTHS})\s+\d{{1,2}},?\s+\d{{4}}     # August 25, 2026
    )""",
    re.IGNORECASE | re.VERBOSE,
)

_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y")

# Keyword → deadline kind (checked in priority order).
_KIND_KEYWORDS: list[tuple[str, list[str]]] = [
    ("submission", ["last date of submission", "bid submission", "submission of bid", "closing"]),
    ("prebid_meeting", ["pre-bid meeting", "pre bid meeting", "prebid"]),
    ("clarification", ["clarification", "pre-bid quer", "query", "seeking clarification"]),
    ("validity", ["bid validity", "validity of bid", "validity period"]),
    ("emd", ["emd", "earnest money"]),
    ("completion_milestone", ["completion", "milestone", "time for completion"]),
]


@dataclass
class DeadlineExtraction:
    kind: str
    due_at: datetime | None
    description: str
    source_page: int | None
    source_quote: str


def parse_date(text: str) -> datetime | None:
    cleaned = text.replace(",", "").strip()
    for fmt in _FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def _classify(line: str) -> str | None:
    low = line.lower()
    for kind, keywords in _KIND_KEYWORDS:
        if any(k in low for k in keywords):
            return kind
    return None


def extract_deadlines(text: str) -> list[DeadlineExtraction]:
    out: list[DeadlineExtraction] = []
    page = 1
    for line in text.splitlines():
        pm = _PAGE.match(line)
        if pm:
            page = int(pm.group(1))
            continue
        kind = _classify(line)
        if kind is None:
            continue
        for m in _DATE_RE.finditer(line):
            due = parse_date(m.group(1))
            out.append(
                DeadlineExtraction(
                    kind=kind,
                    due_at=due,
                    description=line.strip()[:200],
                    source_page=page,
                    source_quote=line.strip()[:200],
                )
            )
    return out
