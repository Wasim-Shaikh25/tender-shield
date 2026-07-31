"""OCP Data Registry corpus adapter (TS-225).

Legality review (2026-07-31):
- Source: https://data.open-contracting.org/ — Open Contracting Partnership bulk
  JSON downloads published under each publisher's open licence.
- Access: public bulk OCDS release packages; no authentication for published data.
- Terms: verify the individual publisher's licence before redistributing derived work;
  OCP registry metadata is open data.
- Rate limit: offline downloads only in CI — no network harvesting from the registry
  index in this adapter (use manual download + ``--path``).

This adapter is a thin wrapper around ``OcdsFileAdapter`` pointed at an unpacked
OCP bulk download directory.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from app.evalcorpus.adapters import AdapterInfo, OcdsFileAdapter
from app.evalcorpus.models import CorpusAward, CorpusDocument, CorpusTender

OCDS_REGISTRY_LEGALITY = (
    "OCP Data Registry bulk OCDS download reviewed 2026-07-31. Public open-data "
    "releases only; verify publisher licence before redistribution. Offline --path "
    "mode — no registry API scraping."
)


class OcdsRegistryAdapter:
    """Harvest OCDS releases from an unpacked OCP Data Registry download."""

    def __init__(self, path: str | Path, *, dataset: str | None = None) -> None:
        if path is None:
            raise ValueError("ocds-registry requires --path to an unpacked download")
        self.path = Path(path)
        label = f"ocds-registry-{dataset}" if dataset else "ocds-registry"
        self._delegate = OcdsFileAdapter(self.path, source_name=label)
        self.info = AdapterInfo(
            name=label,
            version="1.0",
            country="*",
            legality=(
                f"{OCDS_REGISTRY_LEGALITY}"
                + (f" Dataset tag: {dataset}." if dataset else "")
            ),
            requires_network=False,
            min_delay_seconds=0.0,
        )

    def fetch_index(self, *, limit: int | None = None) -> Iterator[CorpusTender]:
        yield from self._delegate.fetch_index(limit=limit)

    def fetch_documents(
        self, tender: CorpusTender
    ) -> Iterator[tuple[CorpusDocument, bytes]]:
        yield from self._delegate.fetch_documents(tender)

    def fetch_awards(self, *, limit: int | None = None) -> Iterator[CorpusAward]:
        yield from self._delegate.fetch_awards(limit=limit)


def ocds_registry_factory(
    *, path: str | Path, dataset: str | None = None
) -> OcdsRegistryAdapter:
    return OcdsRegistryAdapter(path=path, dataset=dataset)
