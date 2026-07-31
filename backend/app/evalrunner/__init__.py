"""Bulk evaluation runner (TS-230).

Runs 1,000+ corpus tenders through the eval pipeline unattended, grades each
with M1 (`app.evalinvariants`), and writes `evals/runs/<run_id>/` per
`specs/eval-at-scale.md` §3.2.

Outside `app/modules/` deliberately — offline evaluation infrastructure, not a
product feature; nothing in the request path imports it.
"""

from app.evalrunner.orchestrator import BatchSummary, cache_key, in_shard, run_batch
from app.evalrunner.pipeline import ClassifiedError, TenderResult, run_tender

__all__ = [
    "BatchSummary",
    "ClassifiedError",
    "TenderResult",
    "cache_key",
    "in_shard",
    "run_batch",
    "run_tender",
]
