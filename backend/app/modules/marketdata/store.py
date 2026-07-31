"""Persist and query harvested marketdata records (TS-196/198/199)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.marketdata.aggregates import MIN_SAMPLE_SIZE, compute_aggregates
from app.modules.marketdata.models import MdAward, MdEmployer, MdProfile, MdTender
from app.modules.marketdata.resolution import ResolutionResult, resolve_buyer


class MarketDataStore:
    def __init__(self, session: Session):
        self.s = session

    def upsert_tender(self, *, ocid: str, **fields) -> MdTender:
        row = self.s.scalar(select(MdTender).where(MdTender.ocid == ocid))
        if row is None:
            row = MdTender(ocid=ocid, **fields)
            self.s.add(row)
        else:
            for key, value in fields.items():
                setattr(row, key, value)
        self.s.commit()
        self.s.refresh(row)
        return row

    def upsert_award(self, *, ocid: str, tender_id: uuid.UUID, **fields) -> MdAward:
        row = self.s.scalar(
            select(MdAward).where(MdAward.ocid == ocid, MdAward.tender_id == tender_id)
        )
        if row is None:
            row = MdAward(ocid=ocid, tender_id=tender_id, **fields)
            self.s.add(row)
        else:
            for key, value in fields.items():
                setattr(row, key, value)
        self.s.commit()
        self.s.refresh(row)
        return row

    def resolve_tender_buyer(
        self,
        tender: MdTender,
        families: dict | None,
    ) -> ResolutionResult:
        result = resolve_buyer(tender.buyer_name, families)
        if result.family is None:
            return result
        employer = self.upsert_employer(
            family=result.family,
            division=result.division,
            region=result.region,
            confidence=result.confidence,
            alias=tender.buyer_name,
        )
        tender.employer_id = employer.id
        self.s.commit()
        self.s.refresh(tender)
        return result

    def upsert_employer(
        self,
        *,
        family: str,
        division: str | None = None,
        region: str | None = None,
        confidence: str = "exact_alias",
        alias: str | None = None,
    ) -> MdEmployer:
        row = self.s.scalar(select(MdEmployer).where(MdEmployer.family == family))
        if row is None:
            aliases = [alias] if alias else []
            row = MdEmployer(
                family=family,
                division=division,
                region=region,
                confidence=confidence,
                aliases=aliases,
            )
            self.s.add(row)
        else:
            if division and not row.division:
                row.division = division
            if region and not row.region:
                row.region = region
            row.confidence = confidence
            if alias and alias not in row.aliases:
                row.aliases = [*row.aliases, alias]
        self.s.commit()
        self.s.refresh(row)
        return row

    def refresh_profile(self, family: str) -> MdProfile | None:
        employer = self.employer_by_family(family)
        if employer is None:
            return None
        records = self._records_for_employer(employer.id)
        sample_size = len(records)
        aggregates = compute_aggregates(records) if records else {}
        row = self.s.scalar(select(MdProfile).where(MdProfile.employer_id == employer.id))
        if row is None:
            row = MdProfile(
                employer_id=employer.id,
                family=family,
                sample_size=sample_size,
                aggregates=aggregates,
            )
            self.s.add(row)
        else:
            row.sample_size = sample_size
            row.aggregates = aggregates
            row.computed_at = datetime.now(UTC)
        self.s.commit()
        self.s.refresh(row)
        return row

    def profile_by_family(self, family: str) -> MdProfile | None:
        return self.s.scalar(select(MdProfile).where(MdProfile.family == family))

    def comparable_pool(self, family: str) -> list[dict]:
        employer = self.employer_by_family(family)
        if employer is None:
            return []
        return self._records_for_employer(employer.id)

    def tender_by_ocid(self, ocid: str) -> MdTender | None:
        return self.s.scalar(select(MdTender).where(MdTender.ocid == ocid))

    def award_prefill(self, tender_ref: str) -> dict | None:
        """Return a one-click-confirm prefill payload for outcomes (TS-216)."""
        ref = tender_ref.strip()
        if not ref:
            return None
        tender = self.s.scalar(select(MdTender).where(MdTender.ocid == ref))
        if tender is None:
            tender = self.s.scalar(select(MdTender).where(MdTender.source_id == ref))
        if tender is None:
            return None
        award = self.s.scalar(
            select(MdAward)
            .where(MdAward.tender_id == tender.id)
            .order_by(MdAward.fetched_at.desc())
        )
        if award is None:
            return None
        return {
            "status": "matched",
            "tender_ref": ref,
            "ocid": tender.ocid,
            "suggested_result": "lost",
            "l1_value_minor": award.value_minor,
            "currency": award.currency,
            "bidder_count": award.bidder_count,
            "winner": award.winner,
            "source_url": award.source_url or tender.source_url,
            "requires_confirmation": True,
        }

    def employer_by_family(self, family: str) -> MdEmployer | None:
        return self.s.scalar(select(MdEmployer).where(MdEmployer.family == family))

    def _records_for_employer(self, employer_id: uuid.UUID) -> list[dict]:
        tenders = list(
            self.s.scalars(select(MdTender).where(MdTender.employer_id == employer_id))
        )
        out: list[dict] = []
        employer = self.s.get(MdEmployer, employer_id)
        for tender in tenders:
            award = self.s.scalar(
                select(MdAward)
                .where(MdAward.tender_id == tender.id)
                .order_by(MdAward.fetched_at.desc())
            )
            if award is None:
                continue
            out.append({
                "ocid": tender.ocid,
                "buyer_name": tender.buyer_name,
                "classification": tender.classification,
                "family": employer.family if employer else None,
                "division": employer.division if employer else None,
                "region": employer.region if employer else None,
                "value_minor": award.value_minor,
                "estimate_minor": tender.value_minor,
                "currency": award.currency,
                "bidder_count": award.bidder_count,
                "award_date": award.award_date,
                "tender_end": tender.tender_end,
                "winner": award.winner,
                "source_url": award.source_url or tender.source_url,
            })
        return out

    @staticmethod
    def suppression_payload(family: str, profile: MdProfile | None) -> dict:
        n = profile.sample_size if profile else 0
        if profile is None or n < MIN_SAMPLE_SIZE:
            return {
                "family": family,
                "status": "insufficient_data",
                "n": n,
                "aggregates": {},
            }
        return {
            "family": family,
            "status": "ok",
            "n": n,
            "aggregates": profile.aggregates,
        }
