"""State NIC eProcurement portal adapter (TS-197).

Legality review (2026-07-31):
- Source: NIC-hosted state eProcurement instances (e.g. mahatenders.gov.in for Maharashtra).
- Access: public active/archive tender listings; no bidder authentication for published notices.
- Terms: respective state government portal terms; public notices are transparency records.
- Rate limit: 1 request / 2 seconds per host (conservative default).
- Parameter ``state`` selects the portal base URL from a built-in registry. Offline ``--path``
  mode reads OCDS/JSON exports with ``source`` tagged ``state-nic-<state>``.

Network mode is best-effort; many instances block datacenter IPs. Offline exports are the
supported CI path.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

from app.evalcorpus.adapters import AdapterInfo, OcdsFileAdapter
from app.evalcorpus.cppp import CpppAdapter
from app.evalcorpus.models import CorpusAward, CorpusDocument, CorpusTender, Provenance

logger = logging.getLogger(__name__)

STATE_NIC_BASES: dict[str, str] = {
    "maharashtra": "https://mahatenders.gov.in/nicgep/app",
    "karnataka": "https://kppp.karnataka.gov.in/nicgep/app",
    "gujarat": "https://tenders.gujarat.gov.in/nicgep/app",
}

STATE_NIC_LEGALITY = (
    "State NIC eProcurement portal reviewed 2026-07-31. Public tender listings only; "
    "robots.txt and 2s/request rate limit; no authentication. Use offline --path when "
    "datacenter egress is blocked."
)


class StateNicAdapter:
    """Parameterised adapter for Indian state NIC procurement portals."""

    def __init__(
        self,
        *,
        state: str = "maharashtra",
        path: str | Path | None = None,
        min_delay_seconds: float = 2.0,
    ) -> None:
        state_key = state.strip().lower()
        if state_key not in STATE_NIC_BASES and path is None:
            raise ValueError(f"unknown state {state!r}; known: {', '.join(STATE_NIC_BASES)}")
        self.state = state_key
        self.path = Path(path) if path else None
        base_url = STATE_NIC_BASES.get(state_key, "")
        self._delegate = (
            OcdsFileAdapter(self.path, source_name=f"state-nic-{state_key}")
            if self.path
            else CpppAdapter(path=None, base_url=base_url, min_delay_seconds=min_delay_seconds)
        )
        self.info = AdapterInfo(
            name=f"state-nic-{state_key}",
            version="1.0",
            country="IN",
            legality=f"{STATE_NIC_LEGALITY} State: {state_key}.",
            requires_network=self.path is None,
            min_delay_seconds=min_delay_seconds,
        )

    def fetch_index(self, *, limit: int | None = None) -> Iterator[CorpusTender]:
        for tender in self._delegate.fetch_index(limit=limit):
            if tender.provenance is not None:
                tender.provenance = Provenance(
                    source=self.info.name,
                    adapter_version=self.info.version,
                    source_url=tender.provenance.source_url,
                    fetched_at=tender.provenance.fetched_at,
                )
            yield tender

    def fetch_documents(
        self, tender: CorpusTender
    ) -> Iterator[tuple[CorpusDocument, bytes]]:
        yield from self._delegate.fetch_documents(tender)

    def fetch_awards(self, *, limit: int | None = None) -> Iterator[CorpusAward]:
        yield from self._delegate.fetch_awards(limit=limit)


def state_nic_factory(
    *,
    state: str = "maharashtra",
    path: str | Path | None = None,
) -> StateNicAdapter:
    return StateNicAdapter(state=state, path=path)
