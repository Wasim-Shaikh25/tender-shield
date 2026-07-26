"""Shared finding contract (Doc §3.2 `findings` table shape).

Lives in core so every producing module (risk, boq) emits the same shape without
importing each other. Writer modules own their `kind`/`category` values.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class FindingKind(StrEnum):
    RISK_CLAUSE = "risk_clause"
    BOQ_DEFECT = "boq_defect"
    SCOPE_GAP = "scope_gap"
    DEADLINE = "deadline"
    MISSING_DOC = "missing_doc"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingSource(StrEnum):
    """The tri-state label enforced in the UI as distinct badges (Doc §11.4)."""

    EXTRACTED_FACT = "extracted_fact"
    DETERMINISTIC_CHECK = "deterministic_check"
    AI_SUGGESTION = "ai_suggestion"


class ReviewStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    FALSE_POSITIVE = "false_positive"
    NEEDS_CLARIFICATION = "needs_clarification"


class Finding(BaseModel):
    kind: FindingKind
    category: str
    severity: Severity
    title: str
    detail: str
    source: FindingSource
    source_page: int | None = None
    source_quote: str | None = Field(default=None, max_length=200)
    boq_item_ids: list[uuid.UUID] = Field(default_factory=list)
    affected_trades: list[str] = Field(default_factory=list)
    suggested_action: str | None = None
    pattern_id: str | None = None
    pattern_version: str | None = None
    amount_exposure: float | None = None
    review_status: ReviewStatus = ReviewStatus.PROPOSED
    review_reason: str | None = None
    explanation: dict | None = None
