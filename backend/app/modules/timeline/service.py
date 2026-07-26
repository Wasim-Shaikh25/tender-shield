"""TimelineService — builds a milestone calendar for an opportunity.

Consumes `ingestion.service_factory` only via the registry. No ingestion imports.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

_KIND_LABELS: dict[str, str] = {
    "tender_published": "Tender published",
    "pre_bid_meeting": "Pre-bid meeting",
    "clarification_cutoff": "Clarification deadline",
    "bid_submission": "Bid submission",
    "technical_opening": "Technical opening",
    "financial_opening": "Financial opening",
    "emd_validity": "EMD validity",
    "bid_validity": "Bid validity",
    "bg_submission": "BG submission",
    "contract_signing": "Contract signing",
    "completion": "Completion milestone",
}

_RAW_TO_CANONICAL: dict[str, str] = {
    "submission": "bid_submission",
    "prebid_meeting": "pre_bid_meeting",
    "clarification": "clarification_cutoff",
    "technical_opening": "technical_opening",
    "financial_opening": "financial_opening",
    "validity": "bid_validity",
    "emd": "emd_validity",
    "emd_validity": "emd_validity",
    "bg_submission": "bg_submission",
    "contract_signing": "contract_signing",
    "completion_milestone": "completion",
}


def _normalize(kind: str) -> str:
    return _RAW_TO_CANONICAL.get(kind, kind)


@dataclass
class TimelineEvent:
    kind: str
    label: str
    due_at: datetime | None
    description: str
    source_page: int | None
    source_quote: str
    confirmed: bool
    source: str  # "extracted" or "synthetic"


class TimelineService:
    def __init__(
        self,
        session: Session,
        *,
        ingestion_factory: Callable[[Session], object] | None = None,
    ):
        self.s = session
        self._ingestion_factory = ingestion_factory

    def _ingestion(self) -> object | None:
        if self._ingestion_factory is None:
            return None
        return self._ingestion_factory(self.s)

    def build(self, org_id, opportunity_id) -> list[TimelineEvent]:
        svc = self._ingestion()
        if svc is None:
            return []

        opp = svc.get_opportunity(org_id, opportunity_id)
        if opp is None:
            return []

        events: list[TimelineEvent] = []
        has_published = False

        for dl in svc.list_deadlines(org_id, opportunity_id):
            kind = _normalize(dl.kind)
            events.append(
                TimelineEvent(
                    kind=kind,
                    label=_KIND_LABELS.get(kind, kind.replace("_", " ").title()),
                    due_at=dl.due_at,
                    description=dl.description or "",
                    source_page=dl.source_page,
                    source_quote=dl.source_quote or "",
                    confirmed=dl.confirmed,
                    source="extracted",
                )
            )
            if kind == "tender_published":
                has_published = True

        # Fallback anchor: when the tender was first recorded.
        if not has_published and opp.created_at is not None:
            events.append(
                TimelineEvent(
                    kind="tender_published",
                    label=_KIND_LABELS["tender_published"],
                    due_at=opp.created_at,
                    description="Tender published (recorded in TenderShield).",
                    source_page=None,
                    source_quote="",
                    confirmed=False,
                    source="synthetic",
                )
            )

        # Stable sort: concrete dates first, then by kind name.
        events.sort(key=lambda e: (e.due_at is None, e.due_at or datetime.min, e.kind))
        return events
