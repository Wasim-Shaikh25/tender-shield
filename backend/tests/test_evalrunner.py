"""Tests for the bulk evaluation runner (TS-230).

Covers the per-tender pipeline (`run_tender`) against real corpus-shaped
records — including the honest "not applicable" BOQ path and every failure
classification — and the orchestrator's resumability, sharding, cross-run
caching, and cost guard.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evalcorpus.adapters import OcdsFileAdapter
from app.evalcorpus.harvest import harvest
from app.evalcorpus.store import CorpusStore
from app.evalrunner.orchestrator import cache_key, in_shard, run_batch
from app.evalrunner.pipeline import run_tender
from app.modules.risk.classifier import NullClassifier
from app.modules.rulepacks.loader import RulePackLoader

PACK = RulePackLoader().get_pack("in-works")

RELEASE_TEMPLATE = {
    "buyer": {"name": "PWD Division I", "address": {"countryName": "India"}},
    "tender": {
        "value": {"amount": "1000.00", "currency": "INR"},
        "tenderPeriod": {"startDate": "2026-07-01T00:00:00Z", "endDate": "2026-08-15T15:00:00Z"},
    },
}


def _seed_corpus(tmp_path: Path, *, n: int = 3, with_boq: bool = False) -> Path:
    """Build a small real corpus via the actual harvester (TS-224), not a
    hand-rolled manifest — so the runner is tested against its real input shape."""
    src = tmp_path / "src"
    src.mkdir()
    # .md, not .pdf: extract_upload reads text files verbatim and skips real PDF
    # parsing, which a hand-written byte string is not valid input for.
    gcc = src / "gcc.md"
    gcc.write_bytes(
        b"[p1]\nGENERAL CONDITIONS OF CONTRACT\n"
        b"[p5]\nLiquidated damages for delay shall be levied at the rate of "
        b"1% per week of the contract value, with no maximum cap."
    )
    documents = [{"url": gcc.as_uri(), "documentType": "gcc", "title": "gcc.md"}]
    if with_boq:
        boq = src / "boq.csv"
        boq.write_text(
            "src_row,item_code,description,unit_raw,qty,rate,amount\n"
            "1,A,concrete work,cum,10,100,1000\n"
        )
        documents.append({"url": boq.as_uri(), "documentType": "boq", "title": "boq.csv"})

    releases = [
        dict(RELEASE_TEMPLATE, ocid=f"ocds-{i}", id=str(i), tender=dict(
            RELEASE_TEMPLATE["tender"], documents=documents
        ))
        for i in range(n)
    ]
    (src / "package.json").write_text(json.dumps({"releases": releases}))

    corpus_root = tmp_path / "corpus"
    harvest(OcdsFileAdapter(src), CorpusStore(corpus_root))
    return corpus_root


@pytest.fixture
def corpus(tmp_path):
    return _seed_corpus(tmp_path)


@pytest.fixture
def corpus_with_boq(tmp_path):
    return _seed_corpus(tmp_path, n=1, with_boq=True)


def _manifest_records(corpus_root: Path) -> list[dict]:
    return CorpusStore(corpus_root).iter_tenders()


# ------------------------------------------------------------------ run_tender


def test_run_tender_ok_on_a_real_harvested_record(corpus):
    store = CorpusStore(corpus)
    record = _manifest_records(corpus)[0]
    result = run_tender(record, store, pack=PACK, classifier=NullClassifier())

    assert result.status == "ok"
    assert result.m1_ok is True
    assert result.documents_processed == 1
    assert result.pages_extracted >= 1
    assert result.rulepack_version == PACK.meta.version
    assert result.started_at and result.finished_at


def test_run_tender_boq_not_applicable_without_a_boq_document(corpus):
    store = CorpusStore(corpus)
    record = _manifest_records(corpus)[0]
    result = run_tender(record, store, pack=PACK, classifier=NullClassifier())
    assert result.boq_status == "not_applicable"


def test_run_tender_checks_a_real_canonical_boq(corpus_with_boq):
    store = CorpusStore(corpus_with_boq)
    record = _manifest_records(corpus_with_boq)[0]
    result = run_tender(record, store, pack=PACK, classifier=NullClassifier())
    assert result.boq_status == "checked"
    assert result.status == "ok"


def test_run_tender_is_deterministic_with_the_null_classifier(corpus):
    store = CorpusStore(corpus)
    record = _manifest_records(corpus)[0]
    a = run_tender(record, store, pack=PACK, classifier=NullClassifier())
    b = run_tender(record, store, pack=PACK, classifier=NullClassifier())
    assert a.findings_count == b.findings_count
    assert a.m1_ok == b.m1_ok == True  # noqa: E712 - explicit for readability


def test_run_tender_handles_a_record_with_no_fetched_documents(corpus):
    """A metadata-only record (sha256 never set) must not crash the run."""
    store = CorpusStore(corpus)
    record = dict(_manifest_records(corpus)[0])
    record["documents"] = [{"url": "https://example.test/x.pdf"}]  # no sha256
    result = run_tender(record, store, pack=PACK, classifier=NullClassifier())
    assert result.status == "ok"
    assert result.documents_processed == 0


def test_run_tender_classifies_a_parse_failure(corpus, monkeypatch):
    store = CorpusStore(corpus)
    record = _manifest_records(corpus)[0]

    def _boom(*a, **kw):
        raise ValueError("corrupt pdf")

    monkeypatch.setattr("app.evalrunner.pipeline.extract_upload", _boom)
    result = run_tender(record, store, pack=PACK, classifier=NullClassifier())
    assert result.status == "failed"
    assert result.failure_reason == "parse_failed"


def test_run_tender_classifies_an_llm_error(corpus):
    store = CorpusStore(corpus)
    record = _manifest_records(corpus)[0]

    class _Exploding:
        def classify(self, pattern, candidates):
            raise RuntimeError("provider 500")

    result = run_tender(record, store, pack=PACK, classifier=_Exploding())
    assert result.status == "failed"
    assert result.failure_reason == "llm_error"


def test_run_tender_classifies_a_timeout(corpus):
    """The classifier is only ever invoked once retrieval finds a candidate
    clause, so the fixture must contain text an anchor query actually matches —
    an empty-document record would short-circuit before `classify()` runs."""
    store = CorpusStore(corpus)
    record = _manifest_records(corpus)[0]  # contains "liquidated damages" text

    class _TimeoutClassifier:
        def classify(self, pattern, candidates):
            raise TimeoutError("provider took too long")

    result = run_tender(record, store, pack=PACK, classifier=_TimeoutClassifier())
    assert result.failure_reason == "timeout"


def test_run_tender_reports_invariant_violation_not_a_crash(corpus, monkeypatch):
    """An M1 violation is a graded failure, distinct from a pipeline crash."""
    store = CorpusStore(corpus)
    record = _manifest_records(corpus)[0]

    import app.evalrunner.pipeline as pipeline_mod

    def _fake_run_m1(bundle):
        from app.evalinvariants import M1Result, Violation

        return M1Result(
            opportunity_id=bundle.opportunity_id,
            violations=[Violation("quote_integrity", "forced failure for the test")],
            checks_run=10,
        )

    monkeypatch.setattr(pipeline_mod, "run_m1", _fake_run_m1)
    result = run_tender(record, store, pack=PACK, classifier=NullClassifier())
    assert result.status == "failed"
    assert result.failure_reason == "invariant_violation"
    assert result.error_detail is None  # it wasn't an exception


def test_run_tender_never_raises_on_an_unclassified_bug(corpus, monkeypatch):
    store = CorpusStore(corpus)
    record = _manifest_records(corpus)[0]
    monkeypatch.setattr(
        "app.evalrunner.pipeline.segment_clauses",
        lambda text: (_ for _ in ()).throw(KeyError("boom")),
    )
    result = run_tender(record, store, pack=PACK, classifier=NullClassifier())
    assert result.status == "failed"
    assert result.failure_reason == "unknown_error"


def test_run_tender_records_cost(corpus):
    store = CorpusStore(corpus)
    record = _manifest_records(corpus)[0]
    result = run_tender(record, store, pack=PACK, classifier=NullClassifier())
    assert result.token_count == 0  # NullClassifier makes no LLM calls
    assert result.fully_priced is True
    assert result.cost_minor == 0


def test_run_tender_result_is_json_serializable(corpus):
    store = CorpusStore(corpus)
    record = _manifest_records(corpus)[0]
    result = run_tender(record, store, pack=PACK, classifier=NullClassifier())
    json.dumps(result.to_dict())  # must not raise


# ---------------------------------------------------------------- orchestrator helpers


def test_in_shard_is_a_deterministic_partition():
    ocids = [f"ocds-{i}" for i in range(200)]
    buckets = [{o for o in ocids if in_shard(o, i, 4)} for i in range(4)]
    assert sum(len(b) for b in buckets) == len(ocids)  # every ocid lands somewhere
    assert set().union(*buckets) == set(ocids)          # nothing lost
    for a in range(4):
        for b in range(a + 1, 4):
            assert buckets[a].isdisjoint(buckets[b])     # nothing duplicated


def test_in_shard_single_shard_selects_everything():
    assert in_shard("anything", 0, 1) is True


def test_cache_key_is_stable_and_input_sensitive():
    k1 = cache_key("ocds-1", "hash-a", "2026.07.1", "none")
    k2 = cache_key("ocds-1", "hash-a", "2026.07.1", "none")
    k3 = cache_key("ocds-1", "hash-b", "2026.07.1", "none")
    assert k1 == k2
    assert k1 != k3


# -------------------------------------------------------------------- run_batch


def test_run_batch_processes_every_tender_and_writes_results(corpus, tmp_path):
    runs_root = tmp_path / "runs"
    summary = run_batch(corpus, runs_root, run_id="r1", model_id="none")

    assert summary.tenders_run == 3
    assert summary.tenders_ok == 3
    assert summary.m1_pass_rate == 1.0

    results_path = runs_root / "r1" / "results.jsonl"
    lines = results_path.read_text().splitlines()
    assert len(lines) == 3
    assert (runs_root / "r1" / "manifest.json").exists()


def test_run_batch_is_resumable(corpus, tmp_path):
    runs_root = tmp_path / "runs"
    run_batch(corpus, runs_root, run_id="resume-test", model_id="none")
    second = run_batch(corpus, runs_root, run_id="resume-test", model_id="none")

    assert second.tenders_resumed_skip == 3
    assert second.tenders_run == 0
    # results.jsonl was not appended a second time
    lines = (runs_root / "resume-test" / "results.jsonl").read_text().splitlines()
    assert len(lines) == 3


def test_run_batch_force_reruns_everything(corpus, tmp_path):
    runs_root = tmp_path / "runs"
    run_batch(corpus, runs_root, run_id="force-test", model_id="none")
    second = run_batch(corpus, runs_root, run_id="force-test", model_id="none", force=True)
    assert second.tenders_run == 3


def test_run_batch_cross_run_cache_is_reused(corpus, tmp_path):
    """A second run with a different run_id, same tenders/rulepack/model, must
    reuse cached results rather than recomputing them."""
    runs_root = tmp_path / "runs"
    run_batch(corpus, runs_root, run_id="run-a", model_id="none")
    second = run_batch(corpus, runs_root, run_id="run-b", model_id="none")
    assert second.tenders_cached == 3
    assert (runs_root / "run-b" / "results.jsonl").exists()


def test_run_batch_shard_selects_a_subset(corpus, tmp_path):
    runs_root = tmp_path / "runs"
    summary = run_batch(corpus, runs_root, run_id="shard-test", shard=(0, 2), model_id="none")
    assert summary.tenders_in_shard < summary.tenders_total


def test_run_batch_limit_caps_the_run(corpus, tmp_path):
    runs_root = tmp_path / "runs"
    summary = run_batch(corpus, runs_root, run_id="limit-test", limit=1, model_id="none")
    assert summary.tenders_run == 1


def test_run_batch_writes_failure_artifacts(tmp_path, monkeypatch):
    """A failing tender gets a per-tender artifact under failures/, not just a
    line buried in results.jsonl."""
    corpus_root = _seed_corpus(tmp_path)
    runs_root = tmp_path / "runs"

    monkeypatch.setattr(
        "app.evalrunner.pipeline.extract_upload",
        lambda *a, **kw: (_ for _ in ()).throw(ValueError("bad file")),
    )
    summary = run_batch(corpus_root, runs_root, run_id="fail-test", model_id="none")

    assert summary.tenders_failed == 3
    assert summary.failure_reasons.get("parse_failed") == 3
    failures_dir = runs_root / "fail-test" / "failures"
    assert len(list(failures_dir.glob("*.json"))) == 3
    payload = json.loads(next(failures_dir.glob("*.json")).read_text())
    assert payload["result"]["failure_reason"] == "parse_failed"
    assert "record" in payload  # enough context to reproduce without re-harvesting


def test_run_batch_cost_guard_aborts_cleanly(corpus, tmp_path, monkeypatch):
    """Exceeding the token budget stops dispatching new work but leaves
    whatever completed intact — never a crash, never silent overspend."""
    import app.evalrunner.tasks as tasks_mod

    def _spendy(record, *, corpus_root, pack_id, model_id):
        from app.evalrunner.pipeline import run_tender
        from app.modules.risk.classifier import NullClassifier
        from app.modules.rulepacks.loader import RulePackLoader

        result = run_tender(
            record,
            CorpusStore(corpus_root),
            pack=RulePackLoader().get_pack(pack_id),
            classifier=NullClassifier(),
        ).to_dict()
        # Force a realistic per-tender token count so the guard has something to
        # trip on, independent of whether the (NullClassifier) run made any real
        # LLM calls.
        result["token_count"] = 1000
        result["cost_minor"] = 0
        result["fully_priced"] = True
        return result

    # Patch the underlying function the Celery task wraps so this stays a pure
    # function call under eager mode rather than needing a live broker.
    monkeypatch.setattr(tasks_mod.process_tender, "run", _spendy)

    runs_root = tmp_path / "runs"
    summary = run_batch(
        corpus, runs_root, run_id="cost-guard-test", model_id="none",
        max_total_tokens=1500, concurrency=1,
    )
    assert summary.aborted_by_cost_guard is True
    assert summary.tenders_run < summary.tenders_in_shard


def test_run_batch_on_an_empty_corpus_is_not_an_error(tmp_path):
    corpus_root = tmp_path / "empty_corpus"
    CorpusStore(corpus_root).ensure()
    runs_root = tmp_path / "runs"
    summary = run_batch(corpus_root, runs_root, run_id="empty-test", model_id="none")
    assert summary.tenders_total == 0
    assert summary.m1_pass_rate is None
