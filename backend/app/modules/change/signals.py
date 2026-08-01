"""Deterministic change-signal classification (TS-246).

Keyword rules only — labels require a verbatim quote span from the input text.
No LLM arithmetic or deadline inference.
"""

from __future__ import annotations

import re

_SIGNAL_KINDS = frozenset(
    {"rfi", "site_instruction", "meeting_minutes", "daily_report", "email"}
)

_REASON_BY_KIND = {
    "rfi": "correspondence",
    "site_instruction": "instruction",
    "meeting_minutes": "correspondence",
    "daily_report": "scope_change",
    "email": "correspondence",
}

_NOTICE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("variation", re.compile(r"\bvariation|change order|revised scope|extra work\b", re.I)),
    ("claim", re.compile(r"\bclaim\b|loss and expense|additional cost\b", re.I)),
    ("extension_of_time", re.compile(r"\bextension of time|\beot\b|delay\b", re.I)),
    ("payment", re.compile(r"\bpayment\b|interim certificate|ra bill\b", re.I)),
]

_TRIGGER_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("site instruction", re.compile(r"\bsite instruction|you are directed|proceed with\b", re.I)),
    ("rfi", re.compile(r"\brfi\b|request for information\b", re.I)),
    ("variation", re.compile(r"\bvariation|change order\b", re.I)),
    ("scope change", re.compile(r"\brevised|amended|additional work\b", re.I)),
]

_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")


def _first_matching_span(text: str, patterns: list[tuple[str, re.Pattern[str]]]) -> tuple[str, str]:
    for label, pattern in patterns:
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - 40)
            end = min(len(text), match.end() + 80)
            span = text[start:end].strip()
            return label, span[:200]
    sentences = [s.strip() for s in _SENTENCE.findall(text) if s.strip()]
    if sentences:
        return "signal", sentences[0][:200]
    return "signal", text[:200]


def classify_signal(signal_kind: str, text: str, *, title: str | None = None) -> dict:
    if signal_kind not in _SIGNAL_KINDS:
        raise ValueError("bad_signal_kind")
    body = (text or "").strip()
    if not body:
        raise ValueError("empty_text")

    notice_type = None
    for category, pattern in _NOTICE_PATTERNS:
        if pattern.search(body):
            notice_type = category
            break

    trigger_label, quote = _first_matching_span(body, _TRIGGER_PATTERNS)
    confidence = "high" if len(quote) >= 20 else "medium"
    if signal_kind in {"meeting_minutes", "daily_report"} and confidence == "high":
        confidence = "medium"

    if title and title.strip():
        event_title = title.strip()
    else:
        kind_label = signal_kind.replace("_", " ").title()
        event_title = f"{kind_label}: {trigger_label}"

    return {
        "title": event_title,
        "reason": _REASON_BY_KIND.get(signal_kind, "other"),
        "notice_type": notice_type or ("variation" if signal_kind == "site_instruction" else None),
        "confidence_band": confidence,
        "source_kind": signal_kind,
        "source_quote": quote,
        "text_preview": body[:500],
    }
