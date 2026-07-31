"""Reproducibility chain helpers (Strategy §C.7, TS-219).

Every finding pins the versions and hashes that produced it so deterministic
stages can be verified byte-identical on re-run and exports can carry the
full accountability chain.
"""

from __future__ import annotations

import hashlib
from importlib.metadata import PackageNotFoundError, version

from pydantic import BaseModel, Field


def get_engine_version() -> str:
    """Application/engine version stamped on every finding."""
    try:
        return version("tendershield")
    except PackageNotFoundError:
        return "0.1.0-dev"


def document_set_hash(sha256_digests: list[str]) -> str:
    """Stable hash of a document set — same algorithm as eval corpus (TS-224)."""
    digests = sorted(d for d in sha256_digests if d)
    return hashlib.sha256("".join(digests).encode()).hexdigest()


def content_hash(text: str) -> str:
    """SHA-256 of arbitrary text (e.g. inline BOQ CSV pasted into the run endpoint)."""
    return hashlib.sha256(text.encode()).hexdigest()


def prompt_hash(system: str, user: str) -> str:
    """Hash of the exact LLM prompt pair used for a classification call."""
    payload = f"system:{system}\nuser:{user}"
    return hashlib.sha256(payload.encode()).hexdigest()


class ProvenanceStamp(BaseModel):
    """Shared provenance fields pinned on every finding from a producer run."""

    rulepack_version: str
    model_id: str = "none"
    prompt_hash: str | None = None
    document_hash: str = ""
    engine_version: str = Field(default_factory=get_engine_version)

    def apply(self, finding):
        """Return a copy of *finding* with provenance fields set."""
        return finding.model_copy(update=self.model_dump())


def stamp_findings(findings: list, stamp: ProvenanceStamp) -> list:
    return [stamp.apply(f) for f in findings]
