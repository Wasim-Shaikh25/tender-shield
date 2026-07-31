# 03 — Evaluation at scale (TS-225, TS-227, TS-228, TS-229, TS-232, TS-233)

**Spec:** `specs/eval-at-scale.md`. **Sprints 1, 2, 8** in `tasks/phase16_tracker.md`.

**Already built — extend, do not rebuild:**

| Package | What it gives you | Task |
|---|---|---|
| `backend/app/evalcorpus/` | OCDS corpus schema, `SourceAdapter` protocol, content-addressed store, harvester | TS-224 ✅ |
| `backend/app/evalinvariants/` | M1 checks, `PipelineBundle`, `run_m1()`, DB adapter | TS-226 ✅ |
| `backend/app/evalrunner/` | `run_tender()`, Celery fan-out, sharding, resume, cost guard | TS-230 ✅ |
| `backend/app/evalrunner/report.py` | `compute_metrics`, `find_baseline`, `diff_metrics` | TS-231 ✅ |
| `scripts/` | `corpus_harvest.py`, `bulk_eval.py`, `eval_report.py` | ✅ |

These packages live **outside `app/modules/`** (alongside `packsdk`) because they are offline
evaluation infrastructure, not product features — nothing in the request path imports them. Keep new
eval work there, not in `app/modules/`.

> **Sequencing rule from the tracker, worth repeating:** correctness (Sprint 2) ships **before**
> revenue (Sprint 5 / Express). Selling reports to strangers with no reviewer, before M1 passes on
> 1,000 real tenders, is *"the single highest-liability sequencing error available in this plan."*

---

## TS-225 — Adapters for 4 sources — **P0**

Same contract and legality discipline as TS-197 (see `02-marketdata.md`). Priority order from
`specs/eval-at-scale.md` §2.2:

| Adapter | Country | Access | Notes |
|---|---|---|---|
| `etimad` | Saudi | **Official API** — Tenders Inquiry Service | Easiest legitimate win; start here |
| `ocds_registry` | 30+ | OCP Data Registry bulk JSON | Mostly done: point `OcdsFileAdapter` at an unpacked archive |
| `cppp` | India | Archive search | Shared with TS-197; the 403 blocker applies |
| `nhai` | India | Free document download | P1 |

`ocds_registry` is closer to "wire up a download + unpack step" than a new adapter, because
`OcdsFileAdapter` already reads release packages, bare release arrays, single releases and `.jsonl`.

**Every adapter needs:** `AdapterInfo.legality` filled in, `min_delay_seconds` honoured, an offline
fixture test, and a `requires_network=False` path so CI never hits the internet.

---

## TS-227 — M2 portal-metadata agreement

**Why it matters:** portals publish structured metadata next to the documents. That metadata *is*
the label. This yields **thousands of free labels** for deadline and value extraction — the two
facts that dominate the first three minutes of user experience.

**New file:** `backend/app/evalinvariants/m2.py` (or `app/evalrunner/m2.py` — put it next to whatever
already holds the per-tender result shape).

```python
class Verdict(StrEnum):
    MATCH            = "match"
    EXTRACTION_MISS  = "extraction_miss"    # we found nothing
    EXTRACTION_WRONG = "extraction_wrong"   # we found a different value
    PORTAL_WRONG     = "portal_wrong"       # metadata contradicts the document
    NO_LABEL         = "no_label"           # portal published nothing — excluded from scoring

@dataclass(frozen=True)
class FieldScore:
    field: str            # submission_deadline | tender_value | emd_amount | tender_ref | buyer | bid_validity
    verdict: Verdict
    extracted: Any
    portal: Any
    detail: str = ""

def score_deadline(extracted: datetime | None, portal: datetime | None) -> FieldScore:
    """Exact match TO THE MINUTE (spec §M2 table). Timezone-aware comparison:
    a naive datetime is a bug, not a near-miss — see the TS-138/TS-152 regressions."""
    if portal is None:
        return FieldScore("submission_deadline", Verdict.NO_LABEL, extracted, portal)
    if extracted is None:
        return FieldScore("submission_deadline", Verdict.EXTRACTION_MISS, None, portal)
    if extracted.tzinfo is None or portal.tzinfo is None:
        raise ValueError("naive datetime in M2 scoring")
    if extracted.replace(second=0, microsecond=0) == portal.replace(second=0, microsecond=0):
        return FieldScore("submission_deadline", Verdict.MATCH, extracted, portal)
    return FieldScore("submission_deadline", Verdict.EXTRACTION_WRONG, extracted, portal)
```

**`portal_wrong` triage is the interesting part** and is easy to skip — don't. When the extracted
value is backed by a **verified verbatim quote** from the document and disagrees with the portal
field, that is evidence the *portal* is wrong. Per the spec that is *"itself a finding worth
surfacing to users."* Rule:

```python
if mismatch and extracted_has_verified_quote:
    verdict = Verdict.PORTAL_WRONG      # requires TS-294 document_id to be trustworthy
```

Currency-aware value comparison: compare **minor units + currency**, never floats.

**Acceptance:** every mismatch lands in exactly one triage bucket; `NO_LABEL` is excluded from the
denominator (a portal that published nothing must not depress the score); gate is ≥95% exact match
on deadline and value.

---

## TS-228 — M3 outcome backtest

**The one thing that makes or breaks this task: split by TIME, not randomly.** Train on awards
before date *T*, test after. A random split leaks — the numbers become meaningless and worse than
having none.

```python
@dataclass(frozen=True)
class Split:
    cutoff: datetime
    train: list[CorpusAward]
    test:  list[CorpusAward]

def time_split(awards: Sequence[CorpusAward], cutoff: datetime) -> Split:
    train = sorted((a for a in awards if a.awarded_at and a.awarded_at <  cutoff), key=...)
    test  = sorted((a for a in awards if a.awarded_at and a.awarded_at >= cutoff), key=...)
    return Split(cutoff, train, test)
```

Metrics (spec §M3): L1 award price MAE/MAPE vs estimate + calibration curve; bidder count MAE;
award latency MAE in days; retender likelihood AUC.

**Depends on TS-199** (marketdata aggregates) — the predictions being backtested come from the
employer graph.

**Acceptance:** the split function is tested for leakage (no test-set award dated before the
cutoff); a baseline is published to `evals/runs/<run_id>/`; metrics the harness cannot compute are
listed as unavailable, never approximated (the TS-231 precedent).

---

## TS-229 — M4 metamorphic checks

Robustness properties needing no ground truth, only two runs. Cheap, and they catch fragility that
accuracy metrics hide.

**Reuse the M1 shapes exactly** — `Violation(invariant, message, finding_ref="", blocking=True)`
from `app/evalinvariants/checks.py`, findings as **plain dicts**, and a `list[Violation]` return.
That way `run_m4` can aggregate identically to `run_m1` in `runner.py`.

```python
# app/evalinvariants/m4.py
import re

from app.evalinvariants.checks import Violation   # public shape; do NOT import checks._norm

def _norm(text: str) -> str:
    """Same normalization checks.py uses. Duplicated deliberately — _norm is private
    to checks.py; if you need it in both places, promote it rather than reaching in."""
    return re.sub(r"\s+", " ", text or "").strip().casefold()

def _key(f: dict) -> tuple:
    """Canonical identity of a finding — NOT its row id or position."""
    return (f.get("pattern_id"), f.get("category"), f.get("severity"),
            _norm(f.get("source_quote") or ""))

def _same_finding_set(a: list[dict], b: list[dict], *, invariant: str) -> list[Violation]:
    sa, sb = {_key(f) for f in a}, {_key(f) for f in b}
    return [Violation(invariant, f"finding set differs: {sorted(sa ^ sb)!r}")] if sa != sb else []

def check_order_invariance(run_a: list[dict], run_b: list[dict]) -> list[Violation]:
    """Shuffling document upload order must not change the finding set."""
    return _same_finding_set(run_a, run_b, invariant="order_invariance")

def check_redundancy_invariance(single: list[dict], duplicated: list[dict]) -> list[Violation]:
    """Uploading the same document twice must not double the findings."""
    return _same_finding_set(single, duplicated, invariant="redundancy_invariance")

def check_addendum_monotonicity(before: list[dict], after: list[dict],
                                changed_clause_ids: set[str]) -> list[Violation]:
    """Applying an addendum may change ONLY findings traceable to changed clauses."""
    delta = {_key(f) for f in before} ^ {_key(f) for f in after}
    changed = {_key(f) for f in (*before, *after) if f.get("clause_id") in changed_clause_ids}
    stray = delta - changed
    return [Violation("addendum_monotonicity",
                      f"addendum changed findings not traceable to it: {sorted(stray)!r}")] if stray else []

def check_format_invariance(native: list[dict], ocred: list[dict]) -> list[Violation]:
    """Same pack native-PDF vs rendered-to-image-and-OCR'd.
    Tolerance applies to quote OFFSETS only — never to the finding set itself."""
    return _same_finding_set(native, ocred, invariant="format_invariance")

def check_locale_invariance(en: list[dict], other: list[dict]) -> list[Violation]:
    """Same clause in EN and AR/HI yields the same CATEGORISED finding.
    Compare (category, severity) only — the quote wording legitimately differs."""
    ka = {(f.get("category"), f.get("severity")) for f in en}
    kb = {(f.get("category"), f.get("severity")) for f in other}
    return [Violation("locale_invariance", f"categorisation differs: {sorted(ka ^ kb)!r}")] if ka != kb else []
```

**Wire into CI as blocking on the 20-tender smoke slice** (that is TS-232, below).

---

## TS-232 — CI gates

Extend `.github/workflows/ci.yml`. The existing `changelog` job is the closest structural model
(conditional job, thin script invocation).

| Cadence | Slice | Modes | Blocking? |
|---|---|---|---|
| Per-PR | 20 tenders | M1 + M4 | **Yes — must be green to merge** |
| Nightly | 100 tenders | M1 + M2 + M4 | Regression diff vs previous night |
| Weekly | 1,000+ | all | Published scorecard |

```yaml
  eval-smoke:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11", cache: pip }
      - name: Install
        run: pip install -e ".[dev,storage,redis,billing,scheduler,celery,auth]"
      - name: M1 + M4 smoke (20 tenders, offline corpus)
        run: |
          python ../scripts/bulk_eval.py \
            --corpus ../evals/corpus --run-id "pr-${{ github.event.pull_request.number }}" \
            --limit 20 --modes m1,m4 --max-total-tokens 0
      - name: Regression gate (>2pt headline drop blocks)
        run: python ../scripts/eval_report.py --run-id "pr-${{ github.event.pull_request.number }}"
```

**Verified against the current scripts before you copy this:**

| Claim | Status |
|---|---|
| `bulk_eval.py` exits non-zero when M1 pass rate < 100% | ✅ real — `if summary.m1_pass_rate < 1.0: return 1` |
| `eval_report.py` exits 1 on regression | ✅ real — documented in its own docstring |
| `bulk_eval.py --modes` | ❌ **does not exist yet — you must add it** as part of TS-232 |

So `--modes m1,m4` in the YAML above is aspirational: add the flag (defaulting to all available
modes) before wiring the job, or drop it and let the smoke run everything. `--max-total-tokens 0`
keeps CI on `NullClassifier` so a PR never spends money — the runner already defaults
`model_id="none"` for exactly this reason.

Nightly/weekly go in a separate workflow file on `schedule:` triggers.

**Acceptance:** a PR that regresses a headline metric >2pt fails; CI never makes a paid model call.

---

## TS-233 — M5 human gold set (50 tenders)

**Calendar-bound, not engineering-bound.** No code dependencies — start it in parallel from Sprint 1
and let it run alongside everything else. This is the long pole for the Phase 16 exit gate.

Composition (spec §M5 — for coverage, not volume):

| Slice | Count | Why |
|---|---|---|
| Known loss-makers (contractor-supplied) | 5 | The only source for *"did it catch the trap that bit"* |
| Government works — CPWD / state PWD | 15 | Primary employer family |
| NHAI / railways | 5 | Different standard forms |
| Private developer | 5 | Different risk calibration |
| Scanned / poor-quality | 5 | OCR degradation honesty |
| MEP / mechanical / supply-and-erection | 10 | Domain-agnosticism proof |
| Saudi (Etimad) / GCC FIDIC | 5 | Pack transfer proof |

Annotate per Build Doc §19; store under `evals/in-works/<slice>/`.

> **Note the tension:** contractor-supplied loss-makers are customer documents, and
> `specs/eval-at-scale.md` §2.3 forbids customer documents in the **corpus**. The gold set is a
> separate store (`evals/in-works/`) with explicit permission — keep the two apart and never let a
> gold-set document leak into a harvest run.

**Exit gate:** gold-set critical-clause recall must meet the Build Doc §19.5 bar. **Kill condition:**
critical-clause recall <75% after two tuning rounds → stop and diagnose before building anything else.
