"""Employer Behaviour Graph service (TS-195 scaffold).

Reference data module — no tenant rows. Until harvest + aggregates land
(TS-196–TS-200) every query degrades to `insufficient_data` rather than
inventing statistics (Strategy §C.1 suppression rule).
"""

from __future__ import annotations

from sqlalchemy.orm import Session


class MarketDataService:
    def __init__(self, session: Session | None = None):
        self.s = session

    def employer_profile(self, family: str) -> dict:
        return {
            "family": family,
            "status": "insufficient_data",
            "n": 0,
            "aggregates": {},
        }

    def comparable_awards(self, opportunity_id, *, employer_family: str | None = None) -> dict:
        return {
            "opportunity_id": str(opportunity_id),
            "status": "insufficient_data",
            "n": 0,
            "filter": {
                "employer_family": employer_family,
                "note": "harvest not yet populated (TS-196+)",
            },
            "awards": [],
        }

    def price_benchmark(self, opportunity_id, *, employer_family: str | None = None) -> dict:
        return {
            "opportunity_id": str(opportunity_id),
            "status": "insufficient_data",
            "n": 0,
            "filter": {"employer_family": employer_family},
            "distribution": {},
        }
