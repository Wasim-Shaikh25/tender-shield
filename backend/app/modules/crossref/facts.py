"""Deterministic canonical-fact extraction for the cross-document
contradiction engine (Strategy Doc §C.5, TS-217).

Every value here is regex-extracted straight from a clause's own stored text —
numbers, dates and percentages are parsed by code, never guessed or computed
by an LLM (CLAUDE.md §4). `source_quote` is always a literal substring of the
clause text it was pulled from, which is what lets the engine "verify" it
later (contradictions.py) without any semantic model in the loop.

Six canonical fact types, matching the backlog's naming (Strategy §C.5):
bid validity, EMD, submission datetime, LD rate, DLP, retention. EMD is split
into `emd_percent` / `emd_amount_minor` because a percentage-of-cost figure
and a flat currency amount are not comparable quantities — conflating them
would produce nonsense "contradictions" between two clauses that both happen
to be correct statements of the same commercial term in different units.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

QUOTE_MAX = 200


@dataclass(frozen=True)
class CanonicalFact:
    fact_type: str
    value: int | float | str
    unit: str
    document_id: str
    document_kind: str
    clause_id: str
    source_page: int | None
    source_quote: str


def _num(raw: str) -> float:
    return float(raw.replace(",", ""))


_VALIDITY_RE = re.compile(
    r"(?:bid|tender|offer)s?\s+shall\s+(?:remain\s+valid|be\s+valid)\s+for\s+"
    r"(?:a\s+period\s+of\s+)?(\d{1,3})\s*(?:\([^)]*\)\s*)?days",
    re.IGNORECASE,
)

_EMD_PERCENT_RE = re.compile(
    r"earnest\s+money\s+deposit[^.]{0,60}?(\d{1,2}(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

_EMD_AMOUNT_RE = re.compile(
    r"earnest\s+money\s+deposit[^.]{0,60}?(?:rs\.?|inr|₹)\s*([\d,]+(?:\.\d+)?)",
    re.IGNORECASE,
)

_LD_RE = re.compile(
    r"liquidated\s+damages[^.]{0,80}?(\d{1,2}(?:\.\d+)?)\s*%\s*(?:per|/)\s*(week|day|month)",
    re.IGNORECASE,
)

_DLP_RE = re.compile(
    r"defect(?:s)?\s+liability\s+period[^.]{0,60}?(\d{1,2})\s*months?",
    re.IGNORECASE,
)

_RETENTION_RE = re.compile(
    r"retention[^.]{0,60}?(\d{1,2}(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

_SUBMISSION_RE = re.compile(
    r"submi(?:t|ssion)[^.]{0,60}?"
    r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})"
    r"(?:\s*(?:up\s*to|at|by)?\s*(\d{1,2}):(\d{2})\s*(hrs?|hours?)?)?",
    re.IGNORECASE,
)


def _extract_bid_validity(text: str) -> list[tuple[str, int | float | str, str]]:
    out: list[tuple[str, int | float | str, str]] = []
    for m in _VALIDITY_RE.finditer(text):
        out.append(("bid_validity_days", int(m.group(1)), m.group(0)))
    return out


def _extract_emd(text: str) -> list[tuple[str, int | float | str, str]]:
    out: list[tuple[str, int | float | str, str]] = []
    for m in _EMD_PERCENT_RE.finditer(text):
        out.append(("emd_percent", _num(m.group(1)), m.group(0)))
    for m in _EMD_AMOUNT_RE.finditer(text):
        # Stored in minor units (paise) — CLAUDE.md §4, money never as float.
        out.append(("emd_amount_minor", round(_num(m.group(1)) * 100), m.group(0)))
    return out


def _extract_ld(text: str) -> list[tuple[str, int | float | str, str]]:
    out: list[tuple[str, int | float | str, str]] = []
    for m in _LD_RE.finditer(text):
        rate, period = m.group(1), m.group(2).lower()
        out.append(("ld_rate_percent", f"{_num(rate)}%/{period}", m.group(0)))
    return out


def _extract_dlp(text: str) -> list[tuple[str, int | float | str, str]]:
    out: list[tuple[str, int | float | str, str]] = []
    for m in _DLP_RE.finditer(text):
        out.append(("dlp_months", int(m.group(1)), m.group(0)))
    return out


def _extract_retention(text: str) -> list[tuple[str, int | float | str, str]]:
    out: list[tuple[str, int | float | str, str]] = []
    for m in _RETENTION_RE.finditer(text):
        out.append(("retention_percent", _num(m.group(1)), m.group(0)))
    return out


def _extract_submission(text: str) -> list[tuple[str, int | float | str, str]]:
    out: list[tuple[str, int | float | str, str]] = []
    for m in _SUBMISSION_RE.finditer(text):
        day, month, year_raw = m.group(1), m.group(2), m.group(3)
        year = int(year_raw) if len(year_raw) == 4 else 2000 + int(year_raw)
        try:
            parsed = date(year, int(month), int(day))
        except ValueError:
            continue  # not a real calendar date — skip rather than guess
        iso = parsed.isoformat()
        if m.group(4) and m.group(5):
            iso = f"{iso}T{int(m.group(4)):02d}:{m.group(5)}"
        out.append(("submission_datetime", iso, m.group(0)))
    return out


_EXTRACTORS = (
    _extract_bid_validity,
    _extract_emd,
    _extract_ld,
    _extract_dlp,
    _extract_retention,
    _extract_submission,
)


def extract_facts(clauses: list[dict]) -> list[CanonicalFact]:
    """`clauses` are plain dicts: {id, document_id, document_kind, text, page_from}."""
    facts: list[CanonicalFact] = []
    for clause in clauses:
        text = clause.get("text") or ""
        if not text:
            continue
        for extractor in _EXTRACTORS:
            for fact_type, value, raw_quote in extractor(text):
                facts.append(
                    CanonicalFact(
                        fact_type=fact_type,
                        value=value,
                        unit=fact_type,
                        document_id=str(clause["document_id"]),
                        document_kind=clause.get("document_kind") or "other",
                        clause_id=str(clause["id"]),
                        source_page=clause.get("page_from"),
                        source_quote=raw_quote[:QUOTE_MAX],
                    )
                )
    return facts
