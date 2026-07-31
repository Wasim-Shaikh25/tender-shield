"""Pack SDK (TS-220): what a third party needs to author and verify a rule-pack
without touching the product's own tests or CI.

Strategy Doc §D.4 — "schema + validator + test harness so a QS consultancy can
write and verify a pack" is what turns domain-agnosticism into distribution
(the pack marketplace) rather than requiring every trade/jurisdiction pack to
be authored in-house.

Two pieces:

* `validate.py` — schema conformance (reuses `RulePackLoader`, which is the
  schema) plus additional lint rules the loader itself doesn't enforce
  (duplicate ids silently overwrite rather than error, for example).
* `packtest.py` — a **deterministic** test harness: BOQ scope-gap and
  trade-checklist matching are pure functions with no LLM involved
  (`app.modules.boq.engine.scope_gaps`), so a pack author can verify that half
  of a pack fully offline, with no API key. Risk-pattern *judgment* (does this
  clause match this pattern?) is LLM-graded and cannot be verified this way —
  that half requires the scale-evaluation harness (`specs/eval-at-scale.md`)
  against real documents, not a unit-test fixture.

Outside `app/modules/` deliberately, matching `evalcorpus`/`evalinvariants`/
`evalrunner` — this is tooling for pack authors, not a product feature, and
nothing in the request path imports it.
"""

from app.packsdk.packtest import PackTestResult, run_pack_tests
from app.packsdk.validate import ValidationReport, validate_pack

__all__ = ["PackTestResult", "ValidationReport", "run_pack_tests", "validate_pack"]
