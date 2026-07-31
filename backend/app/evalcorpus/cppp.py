"""CPPP (Central Public Procurement Portal) corpus adapter (TS-197).

Legality review (2026-07-31):
- Source: https://eprocure.gov.in — Government of India eProcurement portal.
- Access: public tender archive and award records; no authentication for published notices.
- Terms: Government of India website terms apply; public procurement notices are published
  for transparency. Automated access must respect robots.txt and published rate limits.
- Rate limit: 1 request / 2 seconds per host (conservative; no official API documented).
- Network note: datacenter IPs may receive HTTP 403; use an allowed egress path or the
  offline ``--path`` mode with OCDS/JSON exports downloaded manually or via an approved
  data-sharing arrangement. This adapter never attempts to evade blocks.

Offline mode reads OCDS-shaped JSON exports placed in ``--path`` (same shapes as
``OcdsFileAdapter``). Network mode fetches the public active-tenders JSON feed when
reachable.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
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

CPPP_LEGALITY = (
    "CPPP (eprocure.gov.in) public tender archive reviewed 2026-07-31. "
    "Public notices only; robots.txt and 2s/request rate limit; no authentication. "
    "Datacenter egress may be blocked — use allowed egress or offline --path exports."
)

DEFAULT_BASE_URL = "https://eprocure.gov.in/eprocure/app"


class CpppAdapter:
    """Harvest CPPP records from offline exports or the public web feed."""

    def __init__(
        self,
        *,
        path: str | Path | None = None,
        base_url: str = DEFAULT_BASE_URL,
        min_delay_seconds: float = 2.0,
    ) -> None:
        self.path = Path(path) if path else None
        self.base_url = base_url.rstrip("/")
        self._min_delay = min_delay_seconds
        self._file = OcdsFileAdapter(self.path, source_name="cppp") if self.path else None
        self.info = AdapterInfo(
            name="cppp",
            version="1.0",
            country="IN",
            legality=CPPP_LEGALITY,
            requires_network=self.path is None,
            min_delay_seconds=min_delay_seconds,
        )

    def fetch_index(self, *, limit: int | None = None) -> Iterator[CorpusTender]:
        if self._file is not None:
            yield from self._file.fetch_index(limit=limit)
            return
        count = 0
        for release in self._fetch_active_releases(limit=limit):
            tender = tender_from_ocds(
                release,
                source=self.info.name,
                adapter_version=self.info.version,
                source_url=f"{self.base_url}?page=FrontEndLatestActiveTenders",
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
        # Public CPPP document URLs require per-tender navigation; defer to offline exports.
        return
        yield  # pragma: no cover

    def fetch_awards(self, *, limit: int | None = None) -> Iterator[CorpusAward]:
        if self._file is not None:
            yield from self._file.fetch_awards(limit=limit)
            return
        return
        yield  # pragma: no cover

    def _fetch_active_releases(self, *, limit: int | None) -> Iterator[dict]:
        """Best-effort fetch of the public active-tenders JSON feed."""
        url = f"{self.base_url}?page=FrontEndLatestActiveTenders&service=page"
        try:
            raw = self._get(url)
            payload = json.loads(raw)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            logger.warning("cppp network fetch unavailable: %s", exc)
            return
        items = payload if isinstance(payload, list) else payload.get("tenders", [])
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
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")

    @staticmethod
    def _item_to_ocds_release(item: dict) -> dict:
        tender_id = item.get("tenderId") or item.get("id") or item.get("tender_id")
        ocid = f"ocds-cppp-{tender_id}" if tender_id else ""
        return {
            "ocid": ocid,
            "id": str(tender_id or ""),
            "buyer": {
                "name": item.get("organisation") or item.get("buyer", ""),
                "address": {"countryName": "India"},
            },
            "tender": {
                "title": item.get("title") or item.get("tenderTitle") or "",
                "tenderPeriod": {"endDate": item.get("closingDate") or item.get("bidEndDate")},
                "value": {
                    "amount": item.get("estimatedValue") or item.get("value"),
                    "currency": item.get("currency") or "INR",
                },
            },
        }


def cppp_factory(
    *, path: str | Path | None = None, base_url: str = DEFAULT_BASE_URL
) -> CpppAdapter:
    return CpppAdapter(path=path, base_url=base_url)
