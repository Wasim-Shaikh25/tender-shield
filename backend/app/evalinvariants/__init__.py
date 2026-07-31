"""M1 structural invariants (TS-226).

The bulletproof test: ten correctness properties that must hold on any tender,
requiring zero human labels. `specs/eval-at-scale.md` §1 sets the bar at 100%
pass — any violation blocks release.

Outside `app/modules/` deliberately: this is offline evaluation infrastructure,
not a product feature, and nothing in the request path imports it.
"""

from app.evalinvariants.bundle import Artifact, DocPage, PipelineBundle
from app.evalinvariants.checks import ALL_CHECKS, Violation
from app.evalinvariants.db_adapter import bundle_from_opportunity
from app.evalinvariants.runner import M1Result, run_m1

__all__ = [
    "ALL_CHECKS",
    "Artifact",
    "DocPage",
    "M1Result",
    "PipelineBundle",
    "Violation",
    "bundle_from_opportunity",
    "run_m1",
]
