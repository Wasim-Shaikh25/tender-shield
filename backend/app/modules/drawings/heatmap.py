"""Extraction confidence heatmap for drawings (TS-325).

Because we do not have pixel-level CAD/raster analysis in this phase, the heatmap
is derived from text-extraction quality signals: presence of text, title-block
fields, and symbol-assist coverage per page and coarse region.
"""

from __future__ import annotations

import re


def _split_pages(text: str) -> list[tuple[int, str]]:
    marker_re = re.compile(r"\[p(\d+)\]\n")
    if not text:
        return []
    parts = marker_re.split(text)
    pages: list[tuple[int, str]] = []
    if len(parts) > 1:
        current = 1
        for part in parts:
            if part.isdigit():
                current = int(part)
            elif part.strip():
                pages.append((current, part))
                current += 1
    else:
        pages.append((1, text))
    return pages


def _region_confidence(page_text: str, title_block: dict, symbol_total: int) -> dict:
    lines = [line for line in page_text.splitlines() if line.strip()]
    n = len(lines)
    header_end = max(1, n // 6) if n else 0
    body_end = max(2, n * 5 // 6) if n else 0

    def score_for_slice(start: int, end: int) -> float:
        slice_lines = lines[start:end]
        if not slice_lines:
            return 0.0
        text_len = sum(len(line) for line in slice_lines)
        # Base score from text presence.
        score = min(1.0, text_len / 500.0)
        # Boost for title-block fields in header.
        if start == 0:
            filled = sum(1 for v in title_block.values() if v)
            score = min(1.0, score + filled * 0.15)
        # Slight boost if symbols detected on the page.
        if symbol_total:
            score = min(1.0, score + 0.05)
        return round(score, 2)

    return {
        "header": {
            "start_line": 0,
            "end_line": header_end,
            "confidence": score_for_slice(0, header_end) if header_end else 0.0,
        },
        "body": {
            "start_line": header_end,
            "end_line": body_end,
            "confidence": score_for_slice(header_end, body_end) if body_end > header_end else 0.0,
        },
        "footer": {
            "start_line": body_end,
            "end_line": n,
            "confidence": score_for_slice(body_end, n) if n > body_end else 0.0,
        },
    }


def confidence_heatmap(
    extracted_text: str | None,
    title_block: dict,
    symbol_suggestions: dict | None = None,
) -> dict:
    """Return a per-page, per-region confidence heatmap."""
    if not extracted_text:
        return {
            "pages": [],
            "overall_confidence": 0.0,
            "note": "no_extracted_text",
        }

    symbol_total = 0
    if symbol_suggestions:
        symbol_total = sum(symbol_suggestions.get("totals", {}).values())

    pages: list[dict] = []
    overall_scores: list[float] = []
    for page_num, page_text in _split_pages(extracted_text):
        regions = _region_confidence(page_text, title_block, symbol_total)
        page_confidence = round(
            sum(r["confidence"] for r in regions.values()) / len(regions), 2
        ) if regions else 0.0
        overall_scores.append(page_confidence)
        pages.append(
            {
                "page": page_num,
                "confidence": page_confidence,
                "cannot_determine": page_confidence == 0.0,
                "regions": regions,
            }
        )

    overall = round(sum(overall_scores) / len(overall_scores), 2) if overall_scores else 0.0
    return {
        "pages": pages,
        "overall_confidence": overall,
        "note": "Derived from text extraction signals, not pixel overlay.",
    }
