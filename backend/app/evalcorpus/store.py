"""Content-addressed corpus storage and manifest (TS-224).

Documents are stored by ``sha256`` so the same CPWD GCC appearing in a thousand
tenders costs one copy, and so re-harvesting only writes what actually changed.
The manifest is JSONL — appendable, greppable, and diffable between runs, which
matters more here than query power.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.evalcorpus.models import CorpusAward, CorpusTender, sha256_bytes

logger = logging.getLogger(__name__)

#: Present on every manifest line; source adapters must skip records carrying it.
CORPUS_RECORD_MARKER = "_tendershield_corpus_record"

_MANIFEST = "tenders.jsonl"
_AWARDS = "awards.jsonl"
_BLOBS = "blobs"


class CorpusStore:
    """Filesystem corpus: content-addressed blobs plus JSONL manifests.

    Layout::

        <root>/tenders.jsonl        one CorpusTender per line
        <root>/awards.jsonl         one CorpusAward per line
        <root>/blobs/ab/cdef…       document bytes, keyed by sha256
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.blobs = self.root / _BLOBS
        self._seen_ocids: set[str] | None = None

    def ensure(self) -> None:
        self.blobs.mkdir(parents=True, exist_ok=True)

    # -- blobs ------------------------------------------------------------

    def blob_path(self, digest: str) -> Path:
        """Two-level fan-out keeps directory sizes sane at corpus scale."""
        return self.blobs / digest[:2] / digest[2:]

    def has_blob(self, digest: str) -> bool:
        return self.blob_path(digest).exists()

    def put_blob(self, data: bytes) -> tuple[str, bool]:
        """Store bytes, returning (sha256, written). Existing content is not rewritten."""
        digest = sha256_bytes(data)
        path = self.blob_path(digest)
        if path.exists():
            return digest, False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return digest, True

    def read_blob(self, digest: str) -> bytes | None:
        path = self.blob_path(digest)
        return path.read_bytes() if path.exists() else None

    # -- manifests --------------------------------------------------------

    @property
    def manifest_path(self) -> Path:
        return self.root / _MANIFEST

    @property
    def awards_path(self) -> Path:
        return self.root / _AWARDS

    def known_ocids(self) -> set[str]:
        """OCIDs already in the manifest — the basis for resumability."""
        if self._seen_ocids is None:
            seen: set[str] = set()
            if self.manifest_path.exists():
                for line in self.manifest_path.read_text().splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ocid = json.loads(line).get("ocid")
                    except json.JSONDecodeError:
                        continue
                    if ocid:
                        seen.add(str(ocid))
            self._seen_ocids = seen
        return self._seen_ocids

    def append_tender(self, tender: CorpusTender) -> None:
        self.ensure()
        record = tender.to_dict()
        record["document_set_hash"] = tender.document_set_hash
        record["_written_at"] = datetime.now(UTC).isoformat()
        # Marks this line as harvester *output*. A corpus stored inside a scanned
        # source directory would otherwise be re-ingested as input on the next run,
        # because a CorpusTender dict carries an `ocid` and looks like a release.
        record[CORPUS_RECORD_MARKER] = True
        with self.manifest_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        self.known_ocids().add(tender.ocid)

    def append_award(self, award: CorpusAward) -> None:
        self.ensure()
        record = asdict(award)
        record["_written_at"] = datetime.now(UTC).isoformat()
        record[CORPUS_RECORD_MARKER] = True
        with self.awards_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")

    def iter_tenders(self) -> list[dict[str, Any]]:
        if not self.manifest_path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in self.manifest_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("skipping malformed manifest line")
        return out

    def stats(self) -> dict[str, int]:
        tenders = self.iter_tenders()
        blob_count = 0
        if self.blobs.exists():
            blob_count = sum(1 for p in self.blobs.rglob("*") if p.is_file())
        return {
            "tenders": len(tenders),
            "documents": sum(len(t.get("documents") or []) for t in tenders),
            "blobs": blob_count,
        }
