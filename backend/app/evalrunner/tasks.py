"""Celery task wrapping `run_tender` (TS-230).

`app/core/celery.py` falls back to eager (synchronous, in-process) execution
when no Redis broker is configured, so calling this task's `.delay(...).get()`
behaves identically in tests/dev and in a distributed deployment — the
orchestrator does not need two code paths.

Arguments are plain JSON-serializable values (not `RulePack`/classifier objects)
because a real Celery task crosses a broker; `pack_id` and `model_id` are used to
reconstruct both inside the task, mirroring how `ingestion/tasks.py` rebuilds its
session and OCR provider inside the task rather than passing live objects.
"""

from __future__ import annotations

from typing import Any

from app.core.celery import make_celery_app
from app.core.config import Settings
from app.core.llm import openrouter_client
from app.evalcorpus.store import CorpusStore
from app.evalrunner.pipeline import run_tender
from app.modules.risk.classifier import NullClassifier, OpenRouterClassifier
from app.modules.rulepacks.loader import RulePackLoader

app = make_celery_app()


def _build_classifier(model_id: str) -> Any:
    """`model_id="none"` (the default) always yields `NullClassifier` — the
    eval runner never silently spends on a model unless one was explicitly
    requested, since a bulk run is exactly the place an unattended API-key
    surprise would be expensive."""
    if model_id == "none":
        return NullClassifier()
    client = openrouter_client("evalrunner.risk_classify")
    if client is None:
        return NullClassifier()
    return OpenRouterClassifier(model=model_id)


@app.task(name="evalrunner.process_tender")
def process_tender(
    record: dict,
    *,
    corpus_root: str,
    pack_id: str = "in-works",
    model_id: str = "none",
    run_m4_checks: bool = False,
) -> dict:
    store = CorpusStore(corpus_root)
    pack = RulePackLoader().get_pack(pack_id)
    classifier = _build_classifier(model_id)
    result = run_tender(
        record,
        store,
        pack=pack,
        classifier=classifier,
        model_id=model_id,
        settings=Settings(),
        run_m4_checks=run_m4_checks,
    )
    return result.to_dict()
