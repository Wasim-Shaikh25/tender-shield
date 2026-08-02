"""M2 portal-metadata agreement (TS-227).

Compares deterministic extractions from tender text against structured fields
the source portal already published (OCDS / corpus manifest). Mismatches are
triaged into extraction_miss, extraction_wrong, or portal_wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from dateutil.relativedelta import relativedelta

from app.evalcorpus.models import parse_datetime, to_minor_units
from app.modules.ingestion.deadlines import extract_deadlines, parse_date

_TRIAGE = ("extraction_miss", "extraction_wrong", "portal_wrong")

_VALUE_RE = re.compile(
    r"(?:estimated\s+cost|tender\s+value|contract\s+value|amount)[\s:：]+"
    r"(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:rupees?)?\s*(crore|lakh|cr|lac)?",
    re.IGNORECASE,
)

# Duration expressed directly, e.g. "Time for completion: 18 months".
_DURATION_MONTHS_RE = re.compile(
    r"(?:time\s+for\s+completion|contract\s+period|duration|period\s+of\s+completion)"
    r"[\s:：]+"
    r"(\d+(?:\.\d+)?)\s*(?:months?|mos?|m)\b",
    re.IGNORECASE,
)

# Date range, e.g. "Contract period: 01/07/2026 to 15/08/2026".
_DURATION_RANGE_RE = re.compile(
    r"(?:contract\s+period|period\s+of\s+completion|completion\s+period)"
    r"[\s:：]+"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*(?:to|[-–])\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
    re.IGNORECASE,
)


@dataclass
class ExtractedMetadata:
    submission_deadline: datetime | None = None
    value_minor: int | None = None
    currency: str = ""
    tender_ref: str = ""
    buyer_name: str = ""
    project_duration_months: float | None = None


@dataclass
class FieldComparison:
    field: str
    portal_value: str
    extracted_value: str
    match: bool
    triage: str


@dataclass
class M2Result:
    graded_fields: int = 0
    matches: int = 0
    comparisons: list[FieldComparison] = field(default_factory=list)
    triage_counts: dict[str, int] = field(default_factory=dict)

    @property
    def match_rate(self) -> float | None:
        if self.graded_fields == 0:
            return None
        return self.matches / self.graded_fields

    def summary(self) -> dict[str, Any]:
        return {
            "graded_fields": self.graded_fields,
            "matches": self.matches,
            "match_rate": self.match_rate,
            "triage_counts": dict(self.triage_counts),
            "comparisons": [
                {
                    "field": c.field,
                    "portal_value": c.portal_value,
                    "extracted_value": c.extracted_value,
                    "match": c.match,
                    "triage": c.triage,
                }
                for c in self.comparisons
            ],
        }


def _normalize_buyer(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def _scale_amount(amount: float, unit: str | None) -> int | None:
    multiplier = 1.0
    if unit:
        u = unit.lower()
        if u in {"crore", "cr"}:
            multiplier = 10_000_000
        elif u in {"lakh", "lac"}:
            multiplier = 100_000
    return to_minor_units(amount * multiplier, "INR")


def _month_delta(start: datetime, end: datetime) -> float:
    """Approximate month difference, returning a float so 18 months + 1 day > 18."""
    delta = relativedelta(end, start)
    return delta.years * 12 + delta.months + delta.days / 31.0


def _extract_duration_months(text: str) -> float | None:
    # Direct "X months" statement.
    m = _DURATION_MONTHS_RE.search(text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass

    # Date range.
    m = _DURATION_RANGE_RE.search(text)
    if m:
        start = parse_date(m.group(1))
        end = parse_date(m.group(2))
        if start is not None and end is not None and end > start:
            return _month_delta(start, end)

    return None


def extract_metadata_from_text(text: str, *, ocid: str = "") -> ExtractedMetadata:
    """Deterministic metadata extraction from concatenated document text."""
    submission = None
    for row in extract_deadlines(text):
        if row.kind == "submission" and row.due_at:
            submission = row.due_at
            break

    value_minor = None
    currency = ""
    for m in _VALUE_RE.finditer(text):
        raw = m.group(1).replace(",", "")
        try:
            amount = float(raw)
        except ValueError:
            continue
        value_minor = _scale_amount(amount, m.group(2))
        currency = "INR"
        break

    buyer_name = ""
    for line in text.splitlines():
        low = line.lower()
        if "name of employer" in low or "name of authority" in low or low.startswith("buyer:"):
            buyer_name = line.split(":", 1)[-1].strip()[:200]
            break

    project_duration_months = _extract_duration_months(text)

    return ExtractedMetadata(
        submission_deadline=submission,
        value_minor=value_minor,
        currency=currency,
        tender_ref=ocid,
        buyer_name=buyer_name,
        project_duration_months=project_duration_months,
    )


def _parse_portal_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    iso = parse_datetime(raw)
    if iso:
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except ValueError:
            pass
    return parse_date(raw)


def _deadline_match(portal_end: str | None, extracted: datetime | None) -> FieldComparison | None:
    portal_parsed = _parse_portal_datetime(portal_end)
    if portal_parsed is None:
        return None
    if extracted is None:
        return FieldComparison(
            "submission_deadline",
            portal_parsed.isoformat(),
            "",
            False,
            "extraction_miss",
        )
    match = portal_parsed.date() == extracted.date()
    return FieldComparison(
        "submission_deadline",
        portal_parsed.isoformat(),
        extracted.isoformat(),
        match,
        "" if match else "extraction_wrong",
    )


def project_duration_months_from_record(corpus_record: dict) -> float | None:
    """Best-effort project duration in months from explicit or period fields."""
    raw = corpus_record.get("project_duration_months")
    if raw is not None:
        try:
            return float(raw)
        except (TypeError, ValueError):
            pass
    start = _parse_portal_datetime(corpus_record.get("contract_period_start"))
    end = _parse_portal_datetime(corpus_record.get("contract_period_end"))
    if start is not None and end is not None and end > start:
        return _month_delta(start, end)
    return None


def _duration_match(portal_months: float | None, extracted: float | None) -> FieldComparison | None:
    if portal_months is None:
        return None
    if extracted is None:
        return FieldComparison(
            "project_duration_months",
            str(portal_months),
            "",
            False,
            "extraction_miss",
        )
    match = abs(portal_months - extracted) <= 1.0
    return FieldComparison(
        "project_duration_months",
        str(portal_months),
        str(extracted),
        match,
        "" if match else "extraction_wrong",
    )


def score_m2(corpus_record: dict, extracted: ExtractedMetadata) -> M2Result:
    """Compare extracted facts against portal metadata on a corpus manifest row."""
    result = M2Result()
    triage_counts: dict[str, int] = {k: 0 for k in _TRIAGE}

    portal_end = corpus_record.get("tender_end")
    if portal_end:
        cmp = _deadline_match(portal_end, extracted.submission_deadline)
        if cmp is not None:
            result.comparisons.append(cmp)
            result.graded_fields += 1
            if cmp.match:
                result.matches += 1
            elif cmp.triage:
                triage_counts[cmp.triage] += 1

    portal_value = corpus_record.get("value_minor")
    portal_currency = (corpus_record.get("currency") or "").upper()
    if portal_value is not None and portal_currency:
        result.graded_fields += 1
        if extracted.value_minor is None:
            cmp = FieldComparison(
                "tender_value",
                str(portal_value),
                "",
                False,
                "extraction_miss",
            )
            triage_counts["extraction_miss"] += 1
        else:
            match = extracted.value_minor == portal_value and (
                not extracted.currency or extracted.currency == portal_currency
            )
            cmp = FieldComparison(
                "tender_value",
                str(portal_value),
                str(extracted.value_minor),
                match,
                "extraction_wrong" if not match else "",
            )
            if match:
                result.matches += 1
            else:
                triage_counts["extraction_wrong"] += 1
        result.comparisons.append(cmp)

    portal_ocid = corpus_record.get("ocid") or ""
    if portal_ocid:
        result.graded_fields += 1
        extracted_ref = extracted.tender_ref or portal_ocid
        match = portal_ocid == extracted_ref
        cmp = FieldComparison(
            "tender_ref",
            portal_ocid,
            extracted_ref,
            match,
            "extraction_wrong" if not match else "",
        )
        if match:
            result.matches += 1
        elif not match:
            triage_counts["extraction_wrong"] += 1
        result.comparisons.append(cmp)

    buyer_block = corpus_record.get("buyer") or {}
    portal_buyer = buyer_block.get("name") if isinstance(buyer_block, dict) else ""
    if portal_buyer:
        result.graded_fields += 1
        if not extracted.buyer_name:
            cmp = FieldComparison("buyer_name", portal_buyer, "", False, "extraction_miss")
            triage_counts["extraction_miss"] += 1
        else:
            match = _normalize_buyer(portal_buyer) == _normalize_buyer(extracted.buyer_name)
            cmp = FieldComparison(
                "buyer_name",
                portal_buyer,
                extracted.buyer_name,
                match,
                "extraction_wrong" if not match else "",
            )
            if match:
                result.matches += 1
            else:
                triage_counts["extraction_wrong"] += 1
        result.comparisons.append(cmp)

    portal_duration = project_duration_months_from_record(corpus_record)
    cmp = _duration_match(portal_duration, extracted.project_duration_months)
    if cmp is not None:
        result.comparisons.append(cmp)
        result.graded_fields += 1
        if cmp.match:
            result.matches += 1
        elif cmp.triage:
            triage_counts[cmp.triage] += 1

    result.triage_counts = {k: v for k, v in triage_counts.items() if v > 0}
    return result
