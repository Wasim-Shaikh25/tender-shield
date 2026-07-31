"""Employer Behaviour Graph service (TS-195/196)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.marketdata.store import MarketDataStore


class MarketDataService:
    def __init__(self, session: Session | None = None):
        self.s = session
        self._store = MarketDataStore(session) if session is not None else None

    def employer_profile(self, family: str) -> dict:
        if self._store:
            employer = self._store.employer_by_family(family)
            if employer is not None:
                return {
                    "family": employer.family,
                    "division": employer.division,
                    "region": employer.region,
                    "confidence": employer.confidence,
                    "status": "ok",
                    "aliases": employer.aliases,
                }
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
                "note": "aggregates pending TS-199",
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

    def award_prefill(self, tender_ref: str) -> dict | None:
        if self._store is None:
            return None
        return self._store.award_prefill(tender_ref)
