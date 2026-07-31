"""Deterministic employer identity resolution (TS-198)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HONORIFICS = re.compile(
    r"\b(?:e\.?\s*e\.?|er\.?|shri|smt|dr\.?|mr\.?|mrs\.?|ms\.?)\b",
    re.IGNORECASE,
)
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class ResolutionResult:
    family: str | None
    division: str | None
    region: str | None
    confidence: str
    matched_alias: str | None = None


def normalize_buyer_name(name: str, *, abbreviations: dict[str, str] | None = None) -> str:
    text = _HONORIFICS.sub(" ", name.strip())
    text = _WS.sub(" ", text).casefold().strip(" ,.-")
    if abbreviations:
        for abbr, expansion in abbreviations.items():
            key = abbr.casefold().strip()
            if not key:
                continue
            pattern = re.compile(rf"\b{re.escape(key)}\b")
            text = pattern.sub(expansion.casefold(), text)
    return _WS.sub(" ", text).strip()


def resolve_buyer(
    buyer_name: str,
    families: dict | None,
) -> ResolutionResult:
    family_map = (families or {}).get("families") or {}
    if not buyer_name.strip() or not family_map:
        return ResolutionResult(None, None, None, "unresolved")

    all_abbrev: dict[str, str] = {}
    for entry in family_map.values():
        all_abbrev.update(entry.get("abbreviations") or {})

    normalized = normalize_buyer_name(buyer_name, abbreviations=all_abbrev)
    if not normalized:
        return ResolutionResult(None, None, None, "unresolved")

    for family_key, entry in family_map.items():
        for alias in entry.get("aliases") or []:
            alias_norm = normalize_buyer_name(alias, abbreviations=all_abbrev)
            if not alias_norm:
                continue
            if normalized == alias_norm or alias_norm in normalized:
                division = _extract_first(entry.get("division_patterns") or [], normalized)
                region = _extract_first(entry.get("region_patterns") or [], normalized, group=1)
                return ResolutionResult(
                    family_key,
                    division,
                    region,
                    "exact_alias",
                    matched_alias=alias,
                )

    for family_key, entry in family_map.items():
        for alias in entry.get("aliases") or []:
            alias_norm = normalize_buyer_name(alias, abbreviations=all_abbrev)
            if alias_norm and alias_norm in normalized:
                division = _extract_first(entry.get("division_patterns") or [], normalized)
                region = _extract_first(entry.get("region_patterns") or [], normalized, group=1)
                return ResolutionResult(
                    family_key,
                    division,
                    region,
                    "pattern",
                    matched_alias=alias,
                )

    return ResolutionResult(None, None, None, "unresolved")


def _extract_first(patterns: list[str], text: str, *, group: int = 1) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return match.group(group)
            except IndexError:
                return match.group(0)
    return None
