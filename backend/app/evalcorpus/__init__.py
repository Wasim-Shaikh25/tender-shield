"""Evaluation corpus (TS-224).

Harvests public procurement records into an OCDS-shaped, content-addressed corpus
used by the scale evaluation harness (`specs/eval-at-scale.md`).

This package is deliberately outside `app/modules/` — it is offline evaluation
infrastructure, not a product feature, and nothing in the request path imports it.
"""

from app.evalcorpus.harvest import HarvestResult, harvest
from app.evalcorpus.models import CorpusAward, CorpusDocument, CorpusTender
from app.evalcorpus.store import CorpusStore

__all__ = [
    "CorpusAward",
    "CorpusDocument",
    "CorpusStore",
    "CorpusTender",
    "HarvestResult",
    "harvest",
]
