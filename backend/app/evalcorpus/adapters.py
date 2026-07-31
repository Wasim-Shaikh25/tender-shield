"""Corpus source adapters (TS-224 interface; TS-225 real sources).

Every source implements two methods and declares its legal basis. The declaration
is not documentation theatre: `specs/eval-at-scale.md` §2.3 makes legality review a
precondition for shipping an adapter, and `AdapterInfo` is where that review is
recorded so it travels with the code.

Harvest rules that every adapter must satisfy:

* respect ``robots.txt``, published rate limits and terms of use;
* identify itself with a contact-bearing User-Agent;
* **never** authenticate, and never fetch anything the public cannot fetch;
* public records only — customer documents never enter the corpus.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.evalcorpus.models import (
    CorpusAward,
    CorpusDocument,
    CorpusTender,
    awards_from_ocds,
    tender_from_ocds,
)
from app.evalcorpus.store import CORPUS_RECORD_MARKER

USER_AGENT = (
    "TenderShieldCorpusBot/1.0 (evaluation corpus; contact: ops@tendershield.ai)"
)


@dataclass(frozen=True)
class AdapterInfo:
    """Identity and legal basis of a source adapter.

    `legality` must state what was checked and when — the terms of use, whether an
    official API exists, and what the published rate limit is. An adapter without a
    completed review does not ship.
    """

    name: str
    version: str
    country: str
    legality: str
    requires_network: bool = True
    min_delay_seconds: float = 1.0
    max_concurrency: int = 1


class SourceAdapter(Protocol):
    """The two-method contract every source implements."""

    info: AdapterInfo

    def fetch_index(self, *, limit: int | None = None) -> Iterator[CorpusTender]:
        """Yield tender records (metadata only; documents are not yet fetched)."""
        ...

    def fetch_documents(self, tender: CorpusTender) -> Iterator[tuple[CorpusDocument, bytes]]:
        """Yield (document, bytes) pairs for a tender. May yield nothing."""
        ...

    def fetch_awards(self, *, limit: int | None = None) -> Iterator[CorpusAward]:
        """Yield award records where the source publishes them."""
        ...


class OcdsFileAdapter:
    """Reads OCDS releases from local files or directories.

    This is the reference implementation of the adapter contract and the offline
    path used by tests and CI: OCDS bulk downloads from the
    `OCP Data Registry <https://data.open-contracting.org/>`_ are ordinary JSON
    files, so a registry harvest is this adapter pointed at the unpacked download.

    Accepts either an OCDS *release package* (``{"releases": [...]}``), a bare list
    of releases, or a single release object. ``.jsonl`` files are read one release
    per line.
    """

    def __init__(self, path: str | Path, *, source_name: str = "ocds-file") -> None:
        self.path = Path(path)
        self.info = AdapterInfo(
            name=source_name,
            version="1.0",
            country="*",
            legality=(
                "Local files only — no network access. OCDS bulk downloads from the "
                "OCP Data Registry are published as open data under the publisher's "
                "open licence; verify the individual publisher's licence before "
                "redistributing anything derived from them."
            ),
            requires_network=False,
            min_delay_seconds=0.0,
        )

    # -- helpers ----------------------------------------------------------

    def _files(self) -> list[Path]:
        if self.path.is_dir():
            return sorted(
                p for p in self.path.rglob("*") if p.suffix in {".json", ".jsonl"}
            )
        return [self.path] if self.path.exists() else []

    @staticmethod
    def _releases(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            if payload.get(CORPUS_RECORD_MARKER):
                # Harvester output, not a source release — never re-ingest it.
                return []
            releases = payload.get("releases")
            if isinstance(releases, list):
                return [r for r in releases if isinstance(r, dict)]
            if payload.get("ocid"):
                return [payload]
            return []
        if isinstance(payload, list):
            return [r for r in payload if isinstance(r, dict)]
        return []

    def _iter_releases(self) -> Iterator[tuple[dict[str, Any], Path]]:
        for file in self._files():
            try:
                if file.suffix == ".jsonl":
                    for line in file.read_text().splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        for release in self._releases(json.loads(line)):
                            yield release, file
                else:
                    for release in self._releases(json.loads(file.read_text())):
                        yield release, file
            except (json.JSONDecodeError, UnicodeDecodeError):
                # A malformed file must not abort a 1,000-tender harvest.
                continue

    # -- adapter contract -------------------------------------------------

    def fetch_index(self, *, limit: int | None = None) -> Iterator[CorpusTender]:
        count = 0
        for release, file in self._iter_releases():
            if limit is not None and count >= limit:
                return
            tender = tender_from_ocds(
                release,
                source=self.info.name,
                adapter_version=self.info.version,
                source_url=file.as_uri(),
            )
            if not tender.ocid:
                continue
            count += 1
            yield tender

    def fetch_documents(
        self, tender: CorpusTender
    ) -> Iterator[tuple[CorpusDocument, bytes]]:
        """Resolve ``file://`` document URLs; anything remote is left to a network adapter."""
        for doc in tender.documents:
            if not doc.url.startswith("file://"):
                continue
            local = Path(doc.url[len("file://") :])
            if local.exists():
                yield doc, local.read_bytes()

    def fetch_awards(self, *, limit: int | None = None) -> Iterator[CorpusAward]:
        count = 0
        for release, file in self._iter_releases():
            if limit is not None and count >= limit:
                return
            for award in awards_from_ocds(
                release,
                source=self.info.name,
                adapter_version=self.info.version,
                source_url=file.as_uri(),
            ):
                count += 1
                yield award


_REGISTRY: dict[str, Any] = {}


def register(name: str, factory: Any) -> None:
    """Register an adapter factory under a CLI-visible name."""
    _REGISTRY[name] = factory


def available() -> list[str]:
    return sorted(_REGISTRY)


def build(name: str, **kwargs: Any) -> SourceAdapter:
    if name not in _REGISTRY:
        raise KeyError(f"unknown adapter {name!r}; available: {', '.join(available())}")
    adapter: SourceAdapter = _REGISTRY[name](**kwargs)
    return adapter


register("ocds-file", OcdsFileAdapter)

from app.evalcorpus.cppp import cppp_factory  # noqa: E402
from app.evalcorpus.state_nic import state_nic_factory  # noqa: E402

register("cppp", cppp_factory)
register("state-nic", state_nic_factory)
