"""Lightweight, text-based symbol and count assistance for drawings (TS-323).

This is intentionally not pixel-level computer vision. It scans the extracted
page text for commonly-occurring construction symbol labels and reports counts
as suggestions with a `low` confidence and a manual-verification flag.
"""

from __future__ import annotations

import re

# Labels commonly found on MEP/civil drawings that estimators need counts for.
_SYMBOL_PATTERNS = {
    "WD": re.compile(r"\bWD\b", re.IGNORECASE),
    "WS": re.compile(r"\bWS\b", re.IGNORECASE),
    "WP": re.compile(r"\bWP\b", re.IGNORECASE),
    "DW": re.compile(r"\bDW\b", re.IGNORECASE),
    "CB": re.compile(r"\bCB\b", re.IGNORECASE),
    "SP": re.compile(r"\bSP\b", re.IGNORECASE),
    "MCB": re.compile(r"\bMCB\b", re.IGNORECASE),
    "EL": re.compile(r"\bEL\b", re.IGNORECASE),
    "Fan": re.compile(r"\b(?:fan|ceiling\s*fan|exhaust\s*fan)\b", re.IGNORECASE),
    "Light": re.compile(r"\b(?:light|lamp|fixture|LED)\b", re.IGNORECASE),
    "Switch": re.compile(r"\b(?:switch|1g?\s*sw|2g?\s*sw)\b", re.IGNORECASE),
    "RCC": re.compile(r"\bRCC\b", re.IGNORECASE),
    "PCC": re.compile(r"\bPCC\b", re.IGNORECASE),
    "PI": re.compile(r"\bPI\b", re.IGNORECASE),
    "MH": re.compile(r"\b(?:MH|manhole)\b", re.IGNORECASE),
    "GI": re.compile(r"\bGI\s*(?:pipe|conduit|tray)?\b", re.IGNORECASE),
    "PVC": re.compile(r"\bPVC\s*(?:pipe|conduit)?\b", re.IGNORECASE),
}


def _split_pages(text: str) -> list[tuple[int, str]]:
    """Return (page_number, page_text) pairs using [pN] markers."""
    pages: list[tuple[int, str]] = []
    if not text:
        return pages
    marker_re = re.compile(r"\[p(\d+)\]\n")
    parts = marker_re.split(text)
    if len(parts) > 1:
        current = 1
        for part in parts:
            if part.isdigit():
                current = int(part)
            elif part.strip():
                pages.append((current, part))
                current += 1
    else:
        # No markers: treat the whole text as page 1.
        pages.append((1, text))
    return pages


def symbol_assist(extracted_text: str | None) -> dict:
    """Return per-page symbol counts and totals from extracted text."""
    if not extracted_text:
        return {"pages": [], "totals": {}, "note": "no_extracted_text"}

    page_results: list[dict] = []
    totals: dict[str, int] = {}
    for page_num, page_text in _split_pages(extracted_text):
        page_counts: dict[str, int] = {}
        for symbol, pattern in _SYMBOL_PATTERNS.items():
            count = len(pattern.findall(page_text))
            if count:
                page_counts[symbol] = count
                totals[symbol] = totals.get(symbol, 0) + count
        page_results.append(
            {
                "page": page_num,
                "symbols": [
                    {
                        "symbol": s,
                        "count": c,
                        "confidence": "low",
                        "verify_manually": True,
                    }
                    for s, c in page_counts.items()
                ],
            }
        )

    return {
        "pages": page_results,
        "totals": totals,
        "note": (
            "Text-based detection only; counts are suggestions and require "
            "manual verification against the original drawing."
        ),
    }
