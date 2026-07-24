"""Deterministic notice-window extraction (spec baseline B4).

Contractual notice rules — "claim within 14 days", "28 days' notice", "not later
than 7 days" — are the traps that create Phase-3 time-bar countdowns. They are
extracted by regex over the frozen findings' text, NEVER by an LLM (Doc §4:
numbers never come from the model). Each rule carries its normalised day count
and verbatim provenance so it can be trusted by inspection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_UNIT_DAYS = {"day": 1, "week": 7, "month": 30}

# "within 14 days", "not later than 7 working days", "no later than 28 days"
_WITHIN = re.compile(
    r"(?:with[ie]n|not\s+later\s+than|no\s+later\s+than|before\s+the\s+expiry\s+of)\s+"
    r"(\d{1,3})\s+(working\s+)?(day|week|month)s?",
    re.IGNORECASE,
)
# "14 days' notice", "28 days notice", "7 days prior notice"
_NOTICE = re.compile(
    r"(\d{1,3})\s+(working\s+)?(day|week|month)s?[’'\s]*\s*(?:prior\s+)?notice",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NoticeRule:
    days: int
    unit_raw: str
    trigger: str
    category: str
    source_page: int | None
    source_quote: str | None

    def as_dict(self) -> dict:
        return {
            "days": self.days,
            "unit_raw": self.unit_raw,
            "trigger": self.trigger,
            "category": self.category,
            "source_page": self.source_page,
            "source_quote": self.source_quote,
        }


def _normalise(number: str, unit: str) -> int:
    return int(number) * _UNIT_DAYS[unit.lower()]


def _context(text: str, start: int, end: int, width: int = 90) -> str:
    lo = max(0, start - width)
    hi = min(len(text), end + width)
    return " ".join(text[lo:hi].split())


def _scan(text: str) -> list[tuple[int, str, str, str]]:
    """Return (days, unit_raw, trigger_context) tuples for one text blob."""
    hits: list[tuple[int, str, str, str]] = []
    for rx in (_WITHIN, _NOTICE):
        for m in rx.finditer(text):
            number = m.group(1)
            unit = m.group(3)
            unit_raw = f"{'working ' if m.group(2) else ''}{unit.lower()}s"
            days = _normalise(number, unit)
            hits.append((days, unit_raw, _context(text, m.start(), m.end()), m.group(0)))
    return hits


def extract_notice_rules(findings: list[dict]) -> list[NoticeRule]:
    """Extract deduped notice rules from reviewed findings.

    Each finding contributes its `detail` and `source_quote`; provenance
    (source_page/source_quote) is carried from the finding it was found in.
    Deduped by (days, category) — the first occurrence wins so provenance is
    stable and deterministic.
    """
    seen: set[tuple[int, str]] = set()
    rules: list[NoticeRule] = []
    for f in findings:
        category = str(f.get("category") or "other")
        page = f.get("source_page")
        quote = f.get("source_quote")
        blob = " ".join(str(f.get(k) or "") for k in ("title", "detail", "source_quote"))
        for days, unit_raw, trigger, _matched in _scan(blob):
            key = (days, category)
            if key in seen:
                continue
            seen.add(key)
            rules.append(
                NoticeRule(
                    days=days,
                    unit_raw=unit_raw,
                    trigger=trigger,
                    category=category,
                    source_page=page,
                    source_quote=quote,
                )
            )
    rules.sort(key=lambda r: (r.days, r.category))
    return rules
