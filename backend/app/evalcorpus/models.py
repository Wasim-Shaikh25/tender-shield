"""Corpus schema — OCDS-shaped tender records (TS-224).

Normalizing every source into the shape of the
`Open Contracting Data Standard <https://standard.open-contracting.org/>`_ is what
makes the corpus country-agnostic: adapters differ, the corpus does not. OCDS is
implemented by 30+ governments, so for many sources the mapping is the identity
function and for the rest it is a small, explicit translation.

Money follows the product invariant (`CLAUDE.md` §4): **minor units, integer, with
an explicit currency**. OCDS quotes `value.amount` in major units as a decimal, so
conversion happens exactly once, here, at the boundary.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

# ISO 4217 minor-unit exponents that are not 2. Everything unlisted is 2.
_CURRENCY_EXPONENT: dict[str, int] = {
    "JPY": 0,
    "KRW": 0,
    "CLP": 0,
    "ISK": 0,
    "VND": 0,
    "XOF": 0,
    "XAF": 0,
    "BHD": 3,
    "IQD": 3,
    "JOD": 3,
    "KWD": 3,
    "LYD": 3,
    "OMR": 3,
    "TND": 3,
}

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def currency_exponent(currency: str) -> int:
    return _CURRENCY_EXPONENT.get((currency or "").upper(), 2)


def to_minor_units(amount: Any, currency: str) -> int | None:
    """Convert an OCDS major-unit amount to integer minor units.

    Returns None for a missing or unparseable amount — never 0, because "no value
    published" and "worth nothing" are different facts.
    """
    if amount is None or amount == "":
        return None
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        return None
    scaled = value * (10 ** currency_exponent(currency))
    # Round half up, away from zero, without touching float.
    return int(scaled.to_integral_value(rounding="ROUND_HALF_UP"))


def parse_datetime(raw: Any) -> str | None:
    """Normalize an OCDS date/date-time to an ISO-8601 string, or None."""
    if not raw:
        return None
    text = str(raw).strip()
    if not _ISO_DATE.match(text):
        return None
    return text


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class Buyer:
    """The awarding authority, plus our resolution of it into a family/division.

    `family` and `division` stay None until employer resolution runs (TS-198). An
    unresolved buyer is stored unresolved rather than guessed into a family.
    """

    name: str = ""
    identifier: str | None = None
    family: str | None = None
    division: str | None = None
    region: str | None = None


@dataclass
class CorpusDocument:
    """One document attached to a tender. `sha256` is set once bytes are fetched."""

    url: str
    kind: str = "other"          # nit | gcc | scc | boq | spec | addendum | drawing | other
    title: str = ""
    mime: str | None = None
    bytes_len: int | None = None
    sha256: str | None = None
    fetched_at: str | None = None
    http_status: int | None = None
    storage_key: str | None = None
    error: str | None = None

    @property
    def fetched(self) -> bool:
        return self.sha256 is not None


@dataclass
class Provenance:
    """Where a record came from, so any derived finding can be traced back."""

    source: str                   # adapter name, e.g. "ocds", "cppp"
    adapter_version: str
    source_url: str = ""
    fetched_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class CorpusTender:
    """A normalized tender record. `ocid` is the stable cross-source identifier."""

    ocid: str
    source_id: str
    country: str = ""
    jurisdiction: str = ""
    title: str = ""
    buyer: Buyer = field(default_factory=Buyer)
    classification: str = ""       # CPV / NIC / source-native code
    value_minor: int | None = None
    currency: str = ""
    tender_start: str | None = None
    tender_end: str | None = None
    contract_period_start: str | None = None
    contract_period_end: str | None = None
    documents: list[CorpusDocument] = field(default_factory=list)
    provenance: Provenance | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def document_set_hash(self) -> str:
        """Stable hash of the fetched document set — the eval runner's cache key.

        Only fetched documents contribute, so a partially harvested tender does not
        masquerade as a complete one.
        """
        digests = sorted(d.sha256 for d in self.documents if d.sha256)
        return hashlib.sha256("".join(digests).encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CorpusAward:
    """An award record — the ground truth behind the outcome backtest (M3)."""

    ocid: str
    source_id: str
    award_id: str = ""
    date: str | None = None
    suppliers: list[str] = field(default_factory=list)
    value_minor: int | None = None
    currency: str = ""
    bidder_count: int | None = None
    status: str = ""
    provenance: Provenance | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------- OCDS mapping


def _first_value(block: Any) -> tuple[int | None, str]:
    """Extract (minor units, currency) from an OCDS `value` object."""
    if not isinstance(block, dict):
        return None, ""
    currency = str(block.get("currency") or "").upper()
    return to_minor_units(block.get("amount"), currency), currency


def tender_from_ocds(
    release: dict[str, Any], *, source: str, adapter_version: str, source_url: str = ""
) -> CorpusTender:
    """Map one OCDS release to a CorpusTender.

    Unknown or missing fields stay empty rather than being invented — the corpus is
    evaluation ground truth, so a guessed value is worse than an absent one.
    """
    tender = release.get("tender") or {}
    buyer_block = release.get("buyer") or {}
    period = tender.get("tenderPeriod") or {}
    contract = tender.get("contractPeriod") or {}

    value_minor, currency = _first_value(tender.get("value"))

    documents: list[CorpusDocument] = []
    for doc in tender.get("documents") or []:
        if not isinstance(doc, dict):
            continue
        url = str(doc.get("url") or "").strip()
        if not url:
            continue
        documents.append(
            CorpusDocument(
                url=url,
                kind=str(doc.get("documentType") or "other"),
                title=str(doc.get("title") or ""),
                mime=doc.get("format"),
            )
        )

    classifications = tender.get("classification") or {}
    classification = ""
    if isinstance(classifications, dict):
        classification = str(classifications.get("id") or "")

    return CorpusTender(
        ocid=str(release.get("ocid") or ""),
        source_id=str(release.get("id") or release.get("ocid") or ""),
        country=str((buyer_block.get("address") or {}).get("countryName") or ""),
        jurisdiction=str(release.get("language") or ""),
        title=str(tender.get("title") or ""),
        buyer=Buyer(
            name=str(buyer_block.get("name") or ""),
            identifier=str(buyer_block.get("id")) if buyer_block.get("id") else None,
        ),
        classification=classification,
        value_minor=value_minor,
        currency=currency,
        tender_start=parse_datetime(period.get("startDate")),
        tender_end=parse_datetime(period.get("endDate")),
        contract_period_start=parse_datetime(contract.get("startDate")),
        contract_period_end=parse_datetime(contract.get("endDate")),
        documents=documents,
        provenance=Provenance(
            source=source, adapter_version=adapter_version, source_url=source_url
        ),
        raw_metadata={k: v for k, v in release.items() if k not in {"tender", "awards"}},
    )


def awards_from_ocds(
    release: dict[str, Any], *, source: str, adapter_version: str, source_url: str = ""
) -> list[CorpusAward]:
    """Map the `awards` array of an OCDS release to CorpusAward records."""
    out: list[CorpusAward] = []
    for award in release.get("awards") or []:
        if not isinstance(award, dict):
            continue
        value_minor, currency = _first_value(award.get("value"))
        suppliers = [
            str(s.get("name"))
            for s in (award.get("suppliers") or [])
            if isinstance(s, dict) and s.get("name")
        ]
        out.append(
            CorpusAward(
                ocid=str(release.get("ocid") or ""),
                source_id=str(release.get("id") or ""),
                award_id=str(award.get("id") or ""),
                date=parse_datetime(award.get("date")),
                suppliers=suppliers,
                value_minor=value_minor,
                currency=currency,
                status=str(award.get("status") or ""),
                provenance=Provenance(
                    source=source, adapter_version=adapter_version, source_url=source_url
                ),
                raw_metadata={k: v for k, v in award.items() if k != "suppliers"},
            )
        )
    return out
