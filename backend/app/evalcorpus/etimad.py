"""Etimad (Saudi) corpus adapter (TS-225).

Legality review (2026-07-31):
- Source: https://apiportal.etimad.sa — Government of Saudi Arabia procurement API.
- Access: official Tenders Inquiry Service API for published tender metadata.
- Terms: API portal terms apply; public tender notices only; no bidder authentication.
- Rate limit: 1 request / 2 seconds per host (conservative default).
- Network note: API may require registration/API key in production; offline ``--path``
  mode with OCDS/JSON exports is the supported CI path.

Offline mode reads OCDS-shaped JSON exports placed in ``--path``.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

from app.evalcorpus.adapters import USER_AGENT, AdapterInfo, OcdsFileAdapter
from app.evalcorpus.models import (
    CorpusAward,
    CorpusDocument,
    CorpusTender,
    tender_from_ocds,
)

logger = logging.getLogger(__name__)

ETIMAD_LEGALITY = (
    "Etimad (apiportal.etimad.sa) reviewed 2026-07-31. Official public API for "
    "published tenders; 2s/request rate limit; no authentication for public notices. "
    "Use offline --path when API key or egress is unavailable."
)

DEFAULT_BASE_URL = "https://api.etimad.sa/v1"


class EtimadAdapter:
    """Harvest Etimad records from offline exports or the public API."""

    def __init__(
        self,
        *,
        path: str | Path | None = None,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        min_delay_seconds: float = 2.0,
    ) -> None:
        self.path = Path(path) if path else None
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._min_delay = min_delay_seconds
        self._file = (
            OcdsFileAdapter(self.path, source_name="etimad") if self.path else None
        )
        self.info = AdapterInfo(
            name="etimad",
            version="1.0",
            country="SA",
            legality=ETIMAD_LEGALITY,
            requires_network=self.path is None,
            min_delay_seconds=min_delay_seconds,
        )

    def fetch_index(self, *, limit: int | None = None) -> Iterator[CorpusTender]:
        if self._file is not None:
            yield from self._file.fetch_index(limit=limit)
            return
        count = 0
        for release in self._fetch_releases(limit=limit):
            tender = tender_from_ocds(
                release,
                source=self.info.name,
                adapter_version=self.info.version,
                source_url=f"{self.base_url}/tenders",
            )
            if not tender.ocid:
                continue
            count += 1
            yield tender
            if limit is not None and count >= limit:
                return

    def fetch_documents(
        self, tender: CorpusTender
    ) -> Iterator[tuple[CorpusDocument, bytes]]:
        if self._file is not None:
            yield from self._file.fetch_documents(tender)
            return
        return
        yield  # pragma: no cover

    def fetch_awards(self, *, limit: int | None = None) -> Iterator[CorpusAward]:
        if self._file is not None:
            yield from self._file.fetch_awards(limit=limit)
            return
        return
        yield  # pragma: no cover

    def _fetch_releases(self, *, limit: int | None) -> Iterator[dict]:
        """Best-effort fetch of published tender listings."""
        url = f"{self.base_url}/tenders"
        try:
            raw = self._get(url)
            payload = json.loads(raw)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            logger.warning("etimad network fetch unavailable: %s", exc)
            return
        items = payload if isinstance(payload, list) else payload.get("data", [])
        count = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            release = self._item_to_ocds_release(item)
            if release.get("ocid"):
                yield release
                count += 1
                if limit is not None and count >= limit:
                    return

    def _get(self, url: str) -> str:
        time.sleep(self._min_delay)
        headers = {"User-Agent": USER_AGENT}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")

    @staticmethod
    def _item_to_ocds_release(item: dict) -> dict:
        tender_id = item.get("tenderId") or item.get("id") or item.get("referenceNumber")
        ocid = f"ocds-etimad-{tender_id}" if tender_id else ""
        value = item.get("estimatedValue") or item.get("value") or {}
        if not isinstance(value, dict):
            value = {"amount": value, "currency": "SAR"}
        return {
            "ocid": ocid,
            "id": str(tender_id or ""),
            "buyer": {
                "name": item.get("agencyName") or item.get("buyer", ""),
                "address": {"countryName": "Saudi Arabia"},
            },
            "tender": {
                "title": item.get("tenderName") or item.get("title") or "",
                "tenderPeriod": {
                    "endDate": item.get("lastOfferPresentationDate")
                    or item.get("closingDate"),
                },
                "value": value,
            },
        }


def etimad_factory(
    *,
    path: str | Path | None = None,
    base_url: str = DEFAULT_BASE_URL,
    api_key: str | None = None,
) -> EtimadAdapter:
    return EtimadAdapter(path=path, base_url=base_url, api_key=api_key)
