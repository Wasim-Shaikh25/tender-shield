"""Rules-first document classification (Doc §6.1) — pure, no I/O.

Government packs use fixed headers, so anchor regexes classify most files
cheaply; the LLM fallback (not in this slice) handles private-developer packs.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping


def classify_text(text: str, doc_type_anchors: Mapping[str, Iterable[str]]) -> str | None:
    """Return the first doc-type whose any anchor regex matches, else None."""
    for label, patterns in doc_type_anchors.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return label
    return None


def missing_documents(present_kinds: Iterable[str], expected_kinds: Iterable[str]) -> list[str]:
    """Expected doc-types not present in the uploaded set (Doc §1.1 step 2)."""
    present = set(present_kinds)
    return [kind for kind in expected_kinds if kind not in present]
