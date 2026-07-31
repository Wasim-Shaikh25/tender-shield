"""Batch orchestration for the eval runner (TS-230).

Reads a corpus manifest, applies sharding/resume/idempotency-cache filters,
dispatches each tender through the Celery task (in-process when no broker is
configured, distributed otherwise), and writes `evals/runs/<run_id>/` per
`specs/eval-at-scale.md` §3.2. A cost guard stops dispatching new work once a
run-level budget is exceeded, and the run still reports whatever it completed —
"abort cleanly with partial results" rather than "keep spending" or "crash".
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from app.evalcorpus.store import CorpusStore
from app.evalrunner.tasks import process_tender
from app.modules.rulepacks.loader import RulePackLoader

logger = logging.getLogger(__name__)

_CACHE_DIRNAME = "_cache"
_FAILURES_DIRNAME = "failures"
_RESULTS_FILE = "results.jsonl"
_MANIFEST_FILE = "manifest.json"


def cache_key(ocid: str, document_set_hash: str, rulepack_version: str, model_id: str) -> str:
    """Cross-run idempotency key: identical tender + rulepack + model reuses a
    prior result rather than re-running (`specs/eval-at-scale.md` §3.1)."""
    raw = f"{ocid}|{document_set_hash}|{rulepack_version}|{model_id}"
    return hashlib.sha256(raw.encode()).hexdigest()


def in_shard(ocid: str, shard_index: int, shard_count: int) -> bool:
    """Deterministic partition — the same ocid always lands in the same shard,
    so re-running one shard never overlaps another."""
    if shard_count <= 1:
        return True
    digest = int(hashlib.sha256(ocid.encode()).hexdigest(), 16)
    return digest % shard_count == shard_index


@dataclass
class BatchSummary:
    run_id: str
    corpus_root: str
    rulepack_version: str = ""
    model_id: str = "none"
    shard: str = "0/1"
    started_at: str = ""
    finished_at: str = ""
    tenders_total: int = 0
    tenders_in_shard: int = 0
    tenders_run: int = 0
    tenders_cached: int = 0
    tenders_resumed_skip: int = 0
    tenders_ok: int = 0
    tenders_failed: int = 0
    failure_reasons: dict[str, int] = field(default_factory=dict)
    m1_pass_rate: float | None = None
    aborted_by_cost_guard: bool = False
    total_tokens: int = 0
    total_cost_minor: int = 0
    all_fully_priced: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


class _RunDir:
    """Filesystem layout for one run — see `specs/eval-at-scale.md` §3.2."""

    def __init__(self, root: str | Path, run_id: str):
        self.root = Path(root) / run_id
        self.failures = self.root / _FAILURES_DIRNAME
        self.results_path = self.root / _RESULTS_FILE
        self.manifest_path = self.root / _MANIFEST_FILE

    def ensure(self) -> None:
        self.failures.mkdir(parents=True, exist_ok=True)

    def already_processed(self) -> set[str]:
        if not self.results_path.exists():
            return set()
        seen = set()
        for line in self.results_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                seen.add(json.loads(line)["ocid"])
            except (json.JSONDecodeError, KeyError):
                continue
        return seen


def _load_cached(cache_root: Path, key: str) -> dict | None:
    path = cache_root / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _store_cached(cache_root: Path, key: str, result: dict) -> None:
    cache_root.mkdir(parents=True, exist_ok=True)
    (cache_root / f"{key}.json").write_text(json.dumps(result, default=str))


def run_batch(
    corpus_root: str | Path,
    runs_root: str | Path,
    *,
    run_id: str | None = None,
    pack_id: str = "in-works",
    model_id: str = "none",
    shard: tuple[int, int] = (0, 1),
    limit: int | None = None,
    force: bool = False,
    concurrency: int = 4,
    max_total_tokens: int | None = None,
    max_wall_seconds: float | None = None,
) -> BatchSummary:
    """Run every tender in the corpus (filtered by shard/limit) through the eval
    pipeline. Resumable: re-invoking with the same `run_id` skips tenders already
    present in that run's `results.jsonl`."""
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    corpus_root = str(corpus_root)
    store = CorpusStore(corpus_root)
    pack = RulePackLoader().get_pack(pack_id)

    run_dir = _RunDir(runs_root, run_id)
    run_dir.ensure()
    cache_root = Path(runs_root) / _CACHE_DIRNAME

    summary = BatchSummary(
        run_id=run_id,
        corpus_root=corpus_root,
        rulepack_version=pack.meta.version,
        model_id=model_id,
        shard=f"{shard[0]}/{shard[1]}",
        started_at=datetime.now(UTC).isoformat(),
    )

    all_tenders = store.iter_tenders()
    summary.tenders_total = len(all_tenders)
    shard_index, shard_count = shard
    selected = [t for t in all_tenders if in_shard(t.get("ocid", ""), shard_index, shard_count)]
    summary.tenders_in_shard = len(selected)
    if limit is not None:
        selected = selected[:limit]

    already = set() if force else run_dir.already_processed()
    write_lock = Lock()
    run_start = time.monotonic()
    budget_exhausted = False

    def _write_result(record: dict, result: dict) -> None:
        with run_dir.results_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(result, default=str) + "\n")
        if result.get("status") == "failed":
            ocid_safe = result["ocid"].replace("/", "_")
            (run_dir.failures / f"{ocid_safe}.json").write_text(
                json.dumps({"record": record, "result": result}, default=str, indent=2)
            )

    def _process_one(record: dict) -> tuple[str, dict | None]:
        """Returns (outcome, result). outcome is one of "skip_resumed",
        "skip_budget", "cached", "ran" — bookkeeping happens in the caller,
        under the lock, so counters are never mutated from two threads."""
        ocid = record.get("ocid", "")
        if ocid in already:
            return "skip_resumed", None
        if budget_exhausted:
            return "skip_budget", None

        key = cache_key(ocid, record.get("document_set_hash", ""), pack.meta.version, model_id)
        if not force:
            cached = _load_cached(cache_root, key)
            if cached is not None:
                return "cached", cached

        async_result = process_tender.delay(
            record, corpus_root=corpus_root, pack_id=pack_id, model_id=model_id
        )
        # This orchestrator is never itself a Celery task — it is a script/thread
        # pool calling into Celery — so Celery's "don't .get() inside a task"
        # deadlock guard (`disable_sync_subtasks`, on by default) does not apply
        # and is safe to disable here.
        result = async_result.get(disable_sync_subtasks=False)
        _store_cached(cache_root, key, result)
        return "ran", result

    def _handle_result(record: dict, outcome: str, result: dict | None) -> None:
        nonlocal budget_exhausted
        with write_lock:
            if outcome == "skip_resumed":
                summary.tenders_resumed_skip += 1
                return
            if outcome == "skip_budget":
                return
            assert result is not None

            if outcome == "cached":
                summary.tenders_cached += 1

            _write_result(record, result)
            summary.tenders_run += 1
            if result.get("status") == "ok":
                summary.tenders_ok += 1
            else:
                summary.tenders_failed += 1
                reason = result.get("failure_reason") or "unknown_error"
                summary.failure_reasons[reason] = summary.failure_reasons.get(reason, 0) + 1
            summary.total_tokens += int(result.get("token_count") or 0)
            if result.get("fully_priced") is False:
                summary.all_fully_priced = False
            summary.total_cost_minor += int(result.get("cost_minor") or 0)

            if max_total_tokens and summary.total_tokens > max_total_tokens:
                budget_exhausted = True
                summary.aborted_by_cost_guard = True
            if max_wall_seconds and (time.monotonic() - run_start) > max_wall_seconds:
                budget_exhausted = True
                summary.aborted_by_cost_guard = True

    # Fed incrementally (never "submit all, then check") so the cost guard can
    # actually stop new dispatches once it trips: submitting the whole corpus
    # upfront would let workers pick up the next tender before the main thread
    # has processed the result that tripped the guard, defeating it under any
    # concurrency > 1.
    pending = list(selected)
    in_flight: dict = {}

    def _top_up(pool: ThreadPoolExecutor) -> None:
        while pending and len(in_flight) < concurrency and not budget_exhausted:
            record = pending.pop(0)
            in_flight[pool.submit(_process_one, record)] = record

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        _top_up(pool)
        while in_flight:
            done, _ = wait(in_flight, return_when=FIRST_COMPLETED)
            for future in done:
                record = in_flight.pop(future)
                try:
                    outcome, result = future.result()
                except Exception as exc:  # a bug in the runner itself, not a tender
                    logger.exception("unhandled error processing %s", record.get("ocid"))
                    outcome, result = "ran", {
                        "ocid": record.get("ocid", ""),
                        "status": "failed",
                        "failure_reason": "unknown_error",
                        "error_detail": f"{type(exc).__name__}: {exc}",
                    }
                _handle_result(record, outcome, result)
            _top_up(pool)

    if run_dir.results_path.exists():
        m1_values = [
            json.loads(line).get("m1_ok")
            for line in run_dir.results_path.read_text().splitlines()
            if line.strip()
        ]
        m1_graded = [v for v in m1_values if v is not None]
        if m1_graded:
            summary.m1_pass_rate = sum(1 for v in m1_graded if v) / len(m1_graded)

    summary.finished_at = datetime.now(UTC).isoformat()
    run_dir.manifest_path.write_text(json.dumps(summary.to_dict(), default=str, indent=2))
    return summary
