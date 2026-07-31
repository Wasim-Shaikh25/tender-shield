"""Reproducibility chain (TS-219): provenance helpers and finding persistence."""

from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd
import pytest

from app.core.config import Settings
from app.core.contracts.findings import Finding, FindingKind, FindingSource, Severity
from app.core.db import Base, make_engine, make_session_factory
from app.core.provenance import (
    ProvenanceStamp,
    content_hash,
    document_set_hash,
    get_engine_version,
    prompt_hash,
    stamp_findings,
)
from app.modules.boq.engine import normalize, run_checks
from app.modules.boq.service import BoqEngine, BoqRunner
from app.modules.findings.models import FindingRow  # noqa: F401
from app.modules.findings.store import FindingStore
from app.modules.rulepacks.loader import RulePackLoader

SAMPLE = Path(__file__).resolve().parents[2] / "evals" / "in-works" / "sample_tender"


def test_document_set_hash_is_order_independent():
    a = document_set_hash(["bbb", "aaa"])
    b = document_set_hash(["aaa", "bbb"])
    assert a == b
    assert len(a) == 64


def test_prompt_hash_is_stable():
    h1 = prompt_hash("system", "user")
    h2 = prompt_hash("system", "user")
    assert h1 == h2
    assert prompt_hash("system", "other") != h1


def test_engine_version_is_non_empty():
    assert get_engine_version()


def test_stamp_findings_sets_provenance_fields():
    finding = Finding(
        kind=FindingKind.BOQ_DEFECT,
        category="arith",
        severity=Severity.HIGH,
        title="t",
        detail="d",
        source=FindingSource.DETERMINISTIC_CHECK,
    )
    stamp = ProvenanceStamp(
        rulepack_version="2026.07.1",
        model_id="none",
        document_hash=content_hash("csv"),
        engine_version="0.1.0",
    )
    stamped = stamp_findings([finding], stamp)[0]
    assert stamped.rulepack_version == "2026.07.1"
    assert stamped.model_id == "none"
    assert stamped.document_hash == content_hash("csv")
    assert stamped.engine_version == "0.1.0"


@pytest.fixture
def session():
    engine = make_engine(Settings(database_url="sqlite+pysqlite:///:memory:"))
    Base.metadata.create_all(engine)
    return make_session_factory(engine)()


def test_finding_store_persists_provenance(session):
    store = FindingStore(session)
    ws, opp = uuid.uuid4(), uuid.uuid4()
    stamp = ProvenanceStamp(
        rulepack_version="v1",
        model_id="none",
        document_hash="abc123",
    )
    finding = stamp.apply(
        Finding(
            kind=FindingKind.BOQ_DEFECT,
            category="arith",
            severity=Severity.MEDIUM,
            title="x",
            detail="y",
            source=FindingSource.DETERMINISTIC_CHECK,
        )
    )
    store.replace_for_producer(ws, opp, "boq", [finding])
    row = store.list(ws, opp)[0]
    assert row.rulepack_version == "v1"
    assert row.model_id == "none"
    assert row.document_hash == "abc123"
    assert row.engine_version == get_engine_version()


def test_boq_runner_stamps_provenance_and_is_byte_identical_on_rerun(session):
    pack = RulePackLoader().get_pack("in-works")
    engine = BoqEngine(lambda: RulePackLoader(), pack_id="in-works")
    runner = BoqRunner(session, engine=engine, store_factory=None, ingestion_factory=None)
    csv_text = (SAMPLE / "boq.csv").read_text()
    ws, opp = uuid.uuid4(), uuid.uuid4()

    first = runner.run_csv(ws, opp, csv_text)
    second = runner.run_csv(ws, opp, csv_text)

    assert first
    for f in first:
        assert f.rulepack_version == pack.meta.version
        assert f.model_id == "none"
        assert f.prompt_hash is None
        assert f.document_hash == document_set_hash([content_hash(csv_text)])
        assert f.engine_version == get_engine_version()

    def signature(findings):
        return sorted(
            (
                f.kind.value,
                f.category,
                f.severity.value,
                f.title,
                f.detail,
                f.source_page,
                f.source_quote,
                f.amount_exposure,
            )
            for f in findings
        )

    assert signature(first) == signature(second)


def test_boq_engine_deterministic_findings_unchanged_without_provenance():
    """Provenance stamping is additive — core deterministic output is unchanged."""
    pack = RulePackLoader().get_pack("in-works")
    boq_df = pd.read_csv(SAMPLE / "boq.csv")
    out = normalize(boq_df, pack.unit_canon)
    bare = [f.model_dump(exclude_none=True) for f in run_checks(out)]
    stamped = [
        f.model_dump(exclude_none=True)
        for f in stamp_findings(
            run_checks(out),
            ProvenanceStamp(rulepack_version=pack.meta.version, document_hash="x"),
        )
    ]
    for b, s in zip(bare, stamped, strict=True):
        for key in b:
            assert b[key] == s[key]
