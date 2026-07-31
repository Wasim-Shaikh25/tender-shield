"""Tests for the evaluation corpus harvester (TS-224).

Covers the OCDS normalization (especially money, which must be integer minor units
with an explicit currency), content-addressed storage and dedupe, resumability,
provenance, and the harvester's refusal to abort on a single bad record.
"""

from __future__ import annotations

import json

import pytest

from app.evalcorpus import CorpusStore, harvest
from app.evalcorpus.adapters import AdapterInfo, OcdsFileAdapter, available, build
from app.evalcorpus.models import (
    CorpusDocument,
    CorpusTender,
    awards_from_ocds,
    currency_exponent,
    tender_from_ocds,
    to_minor_units,
)

RELEASE = {
    "ocid": "ocds-test-0001",
    "id": "rel-1",
    "buyer": {"name": "PWD Division II", "id": "IN-PWD-2", "address": {"countryName": "India"}},
    "tender": {
        "title": "Construction of office building",
        "value": {"amount": "12345.67", "currency": "INR"},
        "tenderPeriod": {"startDate": "2026-07-01T00:00:00Z", "endDate": "2026-08-15T15:00:00Z"},
        "classification": {"id": "45000000"},
        "documents": [
            {"url": "https://example.test/nit.pdf", "documentType": "nit", "title": "NIT"},
            {"url": "https://example.test/boq.xlsx", "documentType": "boq", "title": "BOQ"},
        ],
    },
    "awards": [
        {
            "id": "award-1",
            "date": "2026-09-20T00:00:00Z",
            "status": "active",
            "value": {"amount": "11000.00", "currency": "INR"},
            "suppliers": [{"name": "Acme Constructions"}],
        }
    ],
}


def _write_package(tmp_path, releases, name="package.json"):
    path = tmp_path / name
    path.write_text(json.dumps({"releases": releases}))
    return path


# ------------------------------------------------------------- money mapping


def test_amount_converts_to_integer_minor_units():
    assert to_minor_units("12345.67", "INR") == 1234567
    assert isinstance(to_minor_units("1", "INR"), int)


def test_zero_decimal_currency():
    assert currency_exponent("JPY") == 0
    assert to_minor_units("1000", "JPY") == 1000


def test_three_decimal_currency():
    assert currency_exponent("KWD") == 3
    assert to_minor_units("1.5", "KWD") == 1500


def test_unknown_currency_defaults_to_two_decimals():
    assert to_minor_units("10", "XYZ") == 1000


def test_missing_amount_is_none_not_zero():
    """'No value published' and 'worth nothing' are different facts."""
    assert to_minor_units(None, "INR") is None
    assert to_minor_units("", "INR") is None
    assert to_minor_units("not-a-number", "INR") is None


def test_rounding_is_half_up():
    assert to_minor_units("0.005", "INR") == 1
    assert to_minor_units("0.004", "INR") == 0


# ------------------------------------------------------------ OCDS → corpus


def test_tender_mapping():
    tender = tender_from_ocds(RELEASE, source="ocds-file", adapter_version="1.0")
    assert tender.ocid == "ocds-test-0001"
    assert tender.title == "Construction of office building"
    assert tender.buyer.name == "PWD Division II"
    assert tender.country == "India"
    assert tender.value_minor == 1234567
    assert tender.currency == "INR"
    assert tender.tender_end.startswith("2026-08-15")
    assert len(tender.documents) == 2
    assert {d.kind for d in tender.documents} == {"nit", "boq"}


def test_buyer_family_stays_unresolved():
    """Employer resolution is TS-198; until then a buyer is stored unresolved."""
    tender = tender_from_ocds(RELEASE, source="s", adapter_version="1.0")
    assert tender.buyer.family is None
    assert tender.buyer.division is None


def test_provenance_is_recorded():
    tender = tender_from_ocds(
        RELEASE, source="ocds-file", adapter_version="1.0", source_url="file:///x.json"
    )
    assert tender.provenance is not None
    assert tender.provenance.source == "ocds-file"
    assert tender.provenance.adapter_version == "1.0"
    assert tender.provenance.source_url == "file:///x.json"
    assert tender.provenance.fetched_at


def test_award_mapping():
    awards = awards_from_ocds(RELEASE, source="s", adapter_version="1.0")
    assert len(awards) == 1
    assert awards[0].suppliers == ["Acme Constructions"]
    assert awards[0].value_minor == 1100000
    assert awards[0].currency == "INR"
    assert awards[0].status == "active"


def test_release_without_documents_maps_cleanly():
    tender = tender_from_ocds({"ocid": "x", "tender": {}}, source="s", adapter_version="1.0")
    assert tender.documents == []
    assert tender.value_minor is None


def test_document_without_url_is_dropped():
    release = {"ocid": "x", "tender": {"documents": [{"documentType": "nit"}]}}
    tender = tender_from_ocds(release, source="s", adapter_version="1.0")
    assert tender.documents == []


def test_document_set_hash_ignores_unfetched_documents():
    """A partially harvested tender must not masquerade as a complete one."""
    tender = CorpusTender(ocid="a", source_id="a")
    empty = tender.document_set_hash
    tender.documents.append(CorpusDocument(url="u"))
    assert tender.document_set_hash == empty
    tender.documents[0].sha256 = "deadbeef"
    assert tender.document_set_hash != empty


# ------------------------------------------------------------------ adapter


def test_adapter_is_registered():
    assert "ocds-file" in available()


def test_build_unknown_adapter_raises():
    with pytest.raises(KeyError):
        build("no-such-adapter")


def test_adapter_declares_its_legal_basis():
    """specs/eval-at-scale.md §2.3 makes legality review a shipping precondition."""
    info = OcdsFileAdapter("/nonexistent").info
    assert isinstance(info, AdapterInfo)
    assert len(info.legality) > 40


def test_fetch_index_reads_a_release_package(tmp_path):
    _write_package(tmp_path, [RELEASE])
    tenders = list(OcdsFileAdapter(tmp_path).fetch_index())
    assert [t.ocid for t in tenders] == ["ocds-test-0001"]


def test_fetch_index_reads_jsonl(tmp_path):
    (tmp_path / "r.jsonl").write_text(json.dumps(RELEASE) + "\n")
    assert len(list(OcdsFileAdapter(tmp_path).fetch_index())) == 1


def test_fetch_index_respects_limit(tmp_path):
    releases = [dict(RELEASE, ocid=f"ocds-{i}", id=str(i)) for i in range(10)]
    _write_package(tmp_path, releases)
    assert len(list(OcdsFileAdapter(tmp_path).fetch_index(limit=3))) == 3


def test_malformed_file_does_not_abort_the_harvest(tmp_path):
    """A bad file in a 1,000-tender corpus must cost one file, not the run."""
    _write_package(tmp_path, [RELEASE], name="good.json")
    (tmp_path / "bad.json").write_text("{not json")
    assert len(list(OcdsFileAdapter(tmp_path).fetch_index())) == 1


def test_release_without_ocid_is_skipped(tmp_path):
    _write_package(tmp_path, [{"id": "no-ocid"}, RELEASE])
    assert len(list(OcdsFileAdapter(tmp_path).fetch_index())) == 1


def test_local_documents_are_resolved(tmp_path):
    doc = tmp_path / "nit.pdf"
    doc.write_bytes(b"%PDF-1.4 tender")
    release = dict(
        RELEASE,
        tender=dict(RELEASE["tender"], documents=[{"url": doc.as_uri(), "documentType": "nit"}]),
    )
    _write_package(tmp_path, [release])
    adapter = OcdsFileAdapter(tmp_path)
    tender = next(iter(adapter.fetch_index()))
    fetched = list(adapter.fetch_documents(tender))
    assert len(fetched) == 1
    assert fetched[0][1] == b"%PDF-1.4 tender"


# -------------------------------------------------------------------- store


def test_blob_is_content_addressed_and_deduped(tmp_path):
    store = CorpusStore(tmp_path / "corpus")
    store.ensure()
    digest_a, written_a = store.put_blob(b"same bytes")
    digest_b, written_b = store.put_blob(b"same bytes")
    assert digest_a == digest_b
    assert written_a is True
    assert written_b is False
    assert store.read_blob(digest_a) == b"same bytes"


def test_blob_fanout_keeps_directories_small(tmp_path):
    store = CorpusStore(tmp_path / "corpus")
    store.ensure()
    digest, _ = store.put_blob(b"x")
    assert store.blob_path(digest).parent.name == digest[:2]


def test_manifest_records_document_set_hash(tmp_path):
    store = CorpusStore(tmp_path / "corpus")
    tender = tender_from_ocds(RELEASE, source="s", adapter_version="1.0")
    store.append_tender(tender)
    record = json.loads(store.manifest_path.read_text().splitlines()[0])
    assert record["ocid"] == "ocds-test-0001"
    assert record["document_set_hash"]
    assert record["_written_at"]


def test_known_ocids_reads_the_manifest(tmp_path):
    store = CorpusStore(tmp_path / "corpus")
    store.append_tender(tender_from_ocds(RELEASE, source="s", adapter_version="1.0"))
    assert "ocds-test-0001" in CorpusStore(tmp_path / "corpus").known_ocids()


# ----------------------------------------------------------------- harvest


def test_harvest_writes_tenders_awards_and_blobs(tmp_path):
    doc = tmp_path / "nit.pdf"
    doc.write_bytes(b"tender bytes")
    release = dict(
        RELEASE,
        tender=dict(RELEASE["tender"], documents=[{"url": doc.as_uri(), "documentType": "nit"}]),
    )
    _write_package(tmp_path, [release])

    store = CorpusStore(tmp_path / "corpus")
    result = harvest(OcdsFileAdapter(tmp_path), store)

    assert result.tenders_written == 1
    assert result.documents_fetched == 1
    assert result.awards_written == 1
    assert store.stats()["tenders"] == 1
    assert result.finished_at


def test_harvest_is_resumable(tmp_path):
    _write_package(tmp_path, [RELEASE])
    store = CorpusStore(tmp_path / "corpus")

    first = harvest(OcdsFileAdapter(tmp_path), store, include_awards=False)
    second = harvest(OcdsFileAdapter(tmp_path), store, include_awards=False)

    assert first.tenders_written == 1
    assert second.tenders_written == 0
    assert second.tenders_skipped == 1


def test_no_resume_reharvests(tmp_path):
    _write_package(tmp_path, [RELEASE])
    store = CorpusStore(tmp_path / "corpus")
    harvest(OcdsFileAdapter(tmp_path), store, include_awards=False)
    again = harvest(OcdsFileAdapter(tmp_path), store, include_awards=False, resume=False)
    assert again.tenders_written == 1


def test_identical_documents_across_tenders_dedupe(tmp_path):
    """The same CPWD GCC in a thousand tenders should cost one copy."""
    shared = tmp_path / "gcc.pdf"
    shared.write_bytes(b"standard general conditions")
    releases = [
        dict(
            RELEASE,
            ocid=f"ocds-{i}",
            id=str(i),
            tender=dict(
                RELEASE["tender"],
                documents=[{"url": shared.as_uri(), "documentType": "gcc"}],
            ),
        )
        for i in range(3)
    ]
    _write_package(tmp_path, releases)

    result = harvest(OcdsFileAdapter(tmp_path), CorpusStore(tmp_path / "corpus"))
    assert result.documents_fetched == 1
    assert result.documents_deduped == 2


def test_document_failure_does_not_abort_the_run(tmp_path):
    _write_package(tmp_path, [RELEASE])

    class Exploding(OcdsFileAdapter):
        def fetch_documents(self, tender):
            raise OSError("network gone")

    result = harvest(Exploding(tmp_path), CorpusStore(tmp_path / "corpus"))
    assert result.document_errors == 1
    assert result.tenders_written == 1  # the tender is still recorded
    assert result.errors


def test_harvest_of_empty_source_is_not_an_error(tmp_path):
    result = harvest(OcdsFileAdapter(tmp_path / "empty"), CorpusStore(tmp_path / "corpus"))
    assert result.tenders_seen == 0
    assert result.errors == []


def test_corpus_inside_the_source_directory_is_not_re_ingested(tmp_path):
    """Regression: the harvester must never read its own manifest as input.

    A CorpusTender record carries an `ocid`, so a manifest line is shaped exactly
    like an OCDS release. With the corpus stored under the scanned directory, the
    second run would otherwise re-harvest its own output and inflate the corpus on
    every pass. Manifest lines carry a marker that source adapters skip.
    """
    _write_package(tmp_path, [RELEASE])
    store = CorpusStore(tmp_path / "corpus")  # deliberately inside the scanned tree

    harvest(OcdsFileAdapter(tmp_path), store, include_awards=False)
    second = harvest(OcdsFileAdapter(tmp_path), store, include_awards=False)
    third = harvest(OcdsFileAdapter(tmp_path), store, include_awards=False)

    assert second.tenders_seen == 1, "manifest line was re-ingested as a release"
    assert third.tenders_seen == 1
    assert store.stats()["tenders"] == 1


def test_award_manifest_is_also_marked(tmp_path):
    _write_package(tmp_path, [RELEASE])
    store = CorpusStore(tmp_path / "corpus")
    harvest(OcdsFileAdapter(tmp_path), store)
    again = harvest(OcdsFileAdapter(tmp_path), store)
    assert again.awards_written == 1  # the one real release, not its own output


def test_metadata_only_mode_skips_documents(tmp_path):
    doc = tmp_path / "nit.pdf"
    doc.write_bytes(b"bytes")
    release = dict(
        RELEASE,
        tender=dict(RELEASE["tender"], documents=[{"url": doc.as_uri(), "documentType": "nit"}]),
    )
    _write_package(tmp_path, [release])
    result = harvest(
        OcdsFileAdapter(tmp_path), CorpusStore(tmp_path / "corpus"), fetch_documents=False
    )
    assert result.documents_fetched == 0
    assert result.tenders_written == 1
