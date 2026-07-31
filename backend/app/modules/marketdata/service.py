"""Employer Behaviour Graph service (TS-195/196/198/199)."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.modules.marketdata.aggregates import MIN_SAMPLE_SIZE
from app.modules.marketdata.comparables import build_comparable_set
from app.modules.marketdata.store import MarketDataStore


class MarketDataService:
    def __init__(
        self,
        session: Session | None = None,
        *,
        loader=None,
        ingestion_factory: Callable | None = None,
        default_pack_id: str = "in-works",
    ):
        self.s = session
        self._store = MarketDataStore(session) if session is not None else None
        self._loader = loader
        self._ingestion_factory = ingestion_factory
        self._default_pack_id = default_pack_id

    def _families(self) -> dict | None:
        if self._loader is None:
            return None
        data = self._loader.employer_families(self._default_pack_id)
        return data.model_dump() if data is not None else None

    def upsert_tender_resolved(self, *, ocid: str, buyer_name: str, **fields):
        if self._store is None:
            return None
        tender = self._store.upsert_tender(ocid=ocid, buyer_name=buyer_name, **fields)
        result = self._store.resolve_tender_buyer(tender, self._families())
        if result.family:
            self._store.refresh_profile(result.family)
        return tender

    def employer_profile(self, family: str) -> dict:
        if self._store is None:
            return self._empty_profile(family)
        employer = self._store.employer_by_family(family)
        profile = self._store.profile_by_family(family)
        if profile is None and employer is not None:
            profile = self._store.refresh_profile(family)
        payload = MarketDataStore.suppression_payload(family, profile)
        if employer is not None:
            payload.update({
                "division": employer.division,
                "region": employer.region,
                "confidence": employer.confidence,
                "aliases": employer.aliases,
            })
        return payload

    def comparable_awards(
        self,
        opportunity_id,
        *,
        employer_family: str | None = None,
        workspace_id=None,
    ) -> dict:
        family = employer_family or self._family_for_opportunity(workspace_id, opportunity_id)
        if self._store is None or not family:
            return {
                "opportunity_id": str(opportunity_id),
                "status": "insufficient_data",
                "n": 0,
                "filter": {"employer_family": family},
                "awards": [],
            }

        pool = self._store.comparable_pool(family)
        if len(pool) < MIN_SAMPLE_SIZE:
            return {
                "opportunity_id": str(opportunity_id),
                "status": "insufficient_data",
                "n": len(pool),
                "filter": {"employer_family": family},
                "awards": [],
            }

        anchor = pool[0]
        awards, filter_dict = build_comparable_set(anchor, pool)
        if len(awards) < MIN_SAMPLE_SIZE:
            return {
                "opportunity_id": str(opportunity_id),
                "status": "insufficient_data",
                "n": len(awards),
                "filter": filter_dict,
                "awards": [],
            }
        return {
            "opportunity_id": str(opportunity_id),
            "status": "ok",
            "n": len(awards),
            "filter": filter_dict,
            "awards": awards,
        }

    def price_benchmark(
        self,
        opportunity_id,
        *,
        employer_family: str | None = None,
        workspace_id=None,
    ) -> dict:
        comparables = self.comparable_awards(
            opportunity_id,
            employer_family=employer_family,
            workspace_id=workspace_id,
        )
        if comparables["status"] != "ok":
            return {
                "opportunity_id": str(opportunity_id),
                "status": "insufficient_data",
                "n": comparables["n"],
                "filter": comparables["filter"],
                "distribution": {},
            }
        values = [a["value_minor"] for a in comparables["awards"] if a.get("value_minor")]
        values.sort()
        return {
            "opportunity_id": str(opportunity_id),
            "status": "ok",
            "n": len(values),
            "filter": comparables["filter"],
            "distribution": {
                "min_minor": values[0] if values else None,
                "max_minor": values[-1] if values else None,
                "median_minor": values[len(values) // 2] if values else None,
            },
        }

    def award_prefill(self, tender_ref: str) -> dict | None:
        if self._store is None:
            return None
        return self._store.award_prefill(tender_ref)

    def resolve_buyer(self, buyer_name: str):
        from app.modules.marketdata.resolution import resolve_buyer

        return resolve_buyer(buyer_name, self._families())

    def _family_for_opportunity(self, workspace_id, opportunity_id) -> str | None:
        if self._ingestion_factory is None or workspace_id is None:
            return None
        svc = self._ingestion_factory(self.s)
        opp = svc.get_opportunity(workspace_id, opportunity_id)
        return getattr(opp, "employer_family", None) if opp else None

    @staticmethod
    def _empty_profile(family: str) -> dict:
        return {
            "family": family,
            "status": "insufficient_data",
            "n": 0,
            "aggregates": {},
        }
