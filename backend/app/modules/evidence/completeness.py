"""Deterministic evidence-completeness scoring (TS-255)."""

from __future__ import annotations

_LABELS: dict[str, str] = {
    "site_instruction": "Site instruction",
    "photograph": "Photograph",
    "geotagged_photo": "Geotagged photo",
    "measurement": "Measurement record",
    "daily_report": "Daily report",
    "meeting_minutes": "Meeting minutes",
    "correspondence": "Correspondence",
    "drawing_revision": "Drawing revision",
    "labour": "Labour record",
    "plant": "Plant/equipment record",
    "material": "Material record",
    "daywork": "Daywork record",
    "other": "Other record",
}

_REQUIRED_BY_REASON: dict[str, list[str]] = {
    "instruction": ["site_instruction", "photograph"],
    "drawing_revision": ["drawing_revision", "photograph", "measurement"],
    "spec_revision": ["correspondence", "photograph"],
    "scope_change": ["site_instruction", "photograph", "measurement", "daily_report"],
    "correspondence": ["correspondence", "photograph"],
}

_DEFAULT_REQUIRED = ["correspondence", "photograph"]


def required_types(reason: str | None) -> list[str]:
    return list(_REQUIRED_BY_REASON.get(reason or "", _DEFAULT_REQUIRED))


def score_completeness(*, reason: str | None, present_types: set[str]) -> dict:
    required = required_types(reason)
    present = [t for t in required if t in present_types]
    missing = [t for t in required if t not in present_types]
    total = len(required) or 1
    score = int(round(100 * len(present) / total))
    return {
        "score": score,
        "required_types": required,
        "present_types": present,
        "missing_types": missing,
        "missing_labels": [_LABELS.get(t, t) for t in missing],
    }
