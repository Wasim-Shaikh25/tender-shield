"""Harvest orchestration (TS-224).

Drives an adapter through index → documents → store, applying the rules in
`specs/eval-at-scale.md` §2.3: polite pacing, content-addressed dedupe, full
provenance, and resumability so a killed 1,000-tender run picks up where it left
off rather than starting again.

A harvest never aborts on a single bad record. A corpus run that dies on tender
417 of 1,000 is worth less than one that finishes and reports 3 failures.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.evalcorpus.adapters import SourceAdapter
from app.evalcorpus.store import CorpusStore

logger = logging.getLogger(__name__)


@dataclass
class HarvestResult:
    """What a harvest actually did — the run's own provenance."""

    adapter: str
    adapter_version: str
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str | None = None
    tenders_seen: int = 0
    tenders_written: int = 0
    tenders_skipped: int = 0        # already in the manifest
    documents_fetched: int = 0
    documents_deduped: int = 0      # bytes already present under that sha256
    document_errors: int = 0
    awards_written: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, object]:
        return {
            "adapter": self.adapter,
            "adapter_version": self.adapter_version,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "tenders_seen": self.tenders_seen,
            "tenders_written": self.tenders_written,
            "tenders_skipped": self.tenders_skipped,
            "documents_fetched": self.documents_fetched,
            "documents_deduped": self.documents_deduped,
            "document_errors": self.document_errors,
            "awards_written": self.awards_written,
            "errors": self.errors[:20],
            "error_count": len(self.errors),
        }


class RateLimiter:
    """Minimum delay between requests to one host. Politeness is not optional."""

    def __init__(self, min_delay_seconds: float) -> None:
        self.min_delay = max(float(min_delay_seconds or 0.0), 0.0)
        self._last: float | None = None

    def wait(self) -> None:
        if self.min_delay <= 0:
            return
        now = time.monotonic()
        if self._last is not None:
            remaining = self.min_delay - (now - self._last)
            if remaining > 0:
                time.sleep(remaining)
        self._last = time.monotonic()


def harvest(
    adapter: SourceAdapter,
    store: CorpusStore,
    *,
    limit: int | None = None,
    fetch_documents: bool = True,
    include_awards: bool = True,
    resume: bool = True,
) -> HarvestResult:
    """Run one harvest cycle. Returns a result even when individual records fail."""
    info = adapter.info
    result = HarvestResult(adapter=info.name, adapter_version=info.version)
    store.ensure()
    limiter = RateLimiter(info.min_delay_seconds)
    known = store.known_ocids() if resume else set()

    for tender in adapter.fetch_index(limit=limit):
        result.tenders_seen += 1

        if resume and tender.ocid in known:
            result.tenders_skipped += 1
            continue

        if fetch_documents:
            try:
                limiter.wait()
                for doc, data in adapter.fetch_documents(tender):
                    digest, written = store.put_blob(data)
                    doc.sha256 = digest
                    doc.bytes_len = len(data)
                    doc.storage_key = digest
                    doc.fetched_at = datetime.now(UTC).isoformat()
                    if written:
                        result.documents_fetched += 1
                    else:
                        result.documents_deduped += 1
            except Exception as exc:  # one bad tender must not kill the run
                result.document_errors += 1
                result.errors.append(f"{tender.ocid}: document fetch failed: {exc}")
                logger.warning("document fetch failed for %s: %s", tender.ocid, exc)

        try:
            store.append_tender(tender)
            result.tenders_written += 1
        except Exception as exc:
            result.errors.append(f"{tender.ocid}: manifest write failed: {exc}")
            logger.exception("manifest write failed for %s", tender.ocid)

    if include_awards:
        try:
            for award in adapter.fetch_awards(limit=limit):
                store.append_award(award)
                result.awards_written += 1
        except Exception as exc:
            result.errors.append(f"award harvest failed: {exc}")
            logger.exception("award harvest failed")

    result.finished_at = datetime.now(UTC).isoformat()
    return result
