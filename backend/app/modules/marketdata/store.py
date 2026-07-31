"""Persist and query harvested marketdata records (TS-196)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.marketdata.models import MdAward, MdEmployer, MdTender


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
