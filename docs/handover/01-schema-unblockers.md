# 01 — Schema unblockers & accountability (TS-294, TS-295, TS-296, TS-219)

**Do these first.** All four touch `findings`, the table every other module writes through. Landing
them together means one migration and one round of writer updates instead of four. Three of them
were discovered *by* the M1 invariant suite and the pricing engine — they are documented gaps, not
speculation.

**Spec to update:** `specs/modules/findings.md` (all four), `specs/data-model.md` (TS-296).
**Files in play:**
- `backend/app/modules/findings/models.py` — the `FindingRow` table
- `backend/app/core/contracts/findings.py` — the shared `Finding` pydantic contract
- Writers: `app/modules/risk/`, `app/modules/boq/`, `app/modules/qualification/`,
  `app/modules/standards/`
- Readers: `app/modules/review/`, `app/modules/export/`, `app/modules/pricing/`,
  `app/evalinvariants/`

> **Do it as ONE alembic revision** covering TS-294/295/296, then TS-219 as a second revision.
> Both `upgrade()` and `downgrade()` must be real — CI runs `alembic downgrade base`.

---

## TS-294 — `Finding.document_id`

**Why.** `check_quote_integrity` in `app/evalinvariants/checks.py` currently verifies "does this page
number, in *any* document attached to the opportunity, contain this quote." Correct for a
single-document opportunity, **weaker when two documents share a page number** — which is every real
tender pack. Provenance is a product invariant (`CLAUDE.md` §4), so this is a correctness gap.

**Change.**

```python
# app/modules/findings/models.py  → FindingRow
document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)

# app/core/contracts/findings.py  → Finding
document_id: uuid.UUID | None = None
```

Nullable, because existing rows have no value and backfilling would mean guessing — which is exactly
what this task exists to stop.

**Writers to update** — every call site that constructs a `Finding` already knows which document it
segmented from; thread it through:

- `risk` — the clause carries its `document_id`; pass it when building the finding.
- `boq` — the BOQ sheet's document id.
- `qualification`, `standards` — same pattern.

**Then tighten the check** in `app/evalinvariants/checks.py`. Note the **real** signatures — checks
return `list[Violation]`, and `bundle.findings` are **plain dicts**, not pydantic models:

```python
# app/evalinvariants/bundle.py — DocPage ALREADY carries document_id, so no bundle
# schema change is needed; only a document-aware lookup alongside the existing pages_at().
    def pages_at(self, page: int, document_id: str | None = None) -> list[DocPage]:
        hits = [p for p in self.pages if p.page == page]
        if document_id is not None:
            hits = [p for p in hits if p.document_id == document_id]
        return hits


# app/evalinvariants/checks.py
def check_quote_integrity(bundle: PipelineBundle) -> list[Violation]:
    violations: list[Violation] = []
    for f in bundle.findings:                       # dicts, keys mirror the Finding contract
        quote = f.get("source_quote")
        if not quote:
            continue
        # TS-294: scope to the finding's own document when it has one.
        pages = bundle.pages_at(f.get("source_page"), f.get("document_id"))
        if not any(_norm(quote) in _norm(p.text) for p in pages):
            violations.append(Violation(
                invariant="quote_integrity",
                message=f"quote not found verbatim on page {f.get('source_page')}",
                finding_ref=str(f.get("id", "")),
            ))
    return violations
```

Legacy rows (`document_id` absent) fall through to the old page-only behaviour — count them so the
scorecard can report how many findings still lack a `document_id`.

**Acceptance**
- A1. A finding written by `risk` carries the `document_id` of the document its clause came from.
- A2. Quote verification resolves against that one document when `document_id` is present.
- A3. Two documents sharing page 7, each with a different quote, no longer cross-satisfy each
  other's verification — this is the regression test that proves the fix.
- A4. Legacy rows (`document_id IS NULL`) still verify under the old rule and are counted in the M1
  summary as `weak_provenance_count`.

---

## TS-295 — `Finding.currency`

**Why.** `check_currency_integrity` can currently only assert `amount_exposure` is an integer.
There is no currency column, so a cross-currency finding is unrepresentable — blocking
multi-jurisdiction work (Strategy §E.2: *jurisdiction is a property of the opportunity, not the
workspace*).

**Change.**

```python
# models.py
currency: Mapped[str | None] = mapped_column(String(3), nullable=True)   # ISO 4217

# contracts/findings.py
currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
```

**Validation rule (state it in the spec, enforce it in the store):**
`amount_exposure IS NOT NULL` ⟹ `currency IS NOT NULL`. A number without its unit is the exact
class of bug the minor-units invariant exists to prevent.

```python
# in the findings store capability, before persisting
if finding.amount_exposure is not None and not finding.currency:
    raise ValueError("amount_exposure requires an explicit currency (TS-295)")
```

**Then tighten** `check_currency_integrity` (real signature — `list[Violation]`, dict findings):

```python
def check_currency_integrity(bundle: PipelineBundle) -> list[Violation]:
    violations: list[Violation] = []
    for f in bundle.findings:
        amount = f.get("amount_exposure")
        if amount is None:
            continue
        if not isinstance(amount, int):
            violations.append(Violation("currency_integrity",
                                        "amount_exposure is not an integer (minor units)"))
        cur = f.get("currency")
        if not cur or len(cur) != 3 or not cur.isupper():
            violations.append(Violation("currency_integrity",
                                        f"amount_exposure without valid ISO 4217 currency: {cur!r}",
                                        finding_ref=str(f.get("id", ""))))
    return violations
```

**Backfill.** Do **not** default existing rows to `"INR"` blindly in the migration. Either leave
NULL and let the validation apply to new writes only, or backfill from the owning opportunity's
jurisdiction if that is unambiguous — and say which you did in the migration docstring.

**Acceptance**
- A1. A finding with `amount_exposure` and no currency is rejected at the store boundary.
- A2. `check_currency_integrity` fails a bundle containing such a finding.
- A3. Two findings in different currencies on one opportunity round-trip correctly.

---

## TS-296 — `Finding.facts` + `Opportunity.contract_value_minor`

**Why.** `app/modules/pricing/loading.py` needs structured facts (LD rate, cap percent, payment
days) and the contract value to compute a loading. Neither is persisted, so
`GET /api/pricing/opportunities/{id}/loading` currently takes them as **caller-supplied query
parameters** — see the apology in `pricing/router.py`'s docstring. This task removes that crutch.

**Change.**

```python
# app/modules/findings/models.py
facts: Mapped[dict | None] = mapped_column(JSON, nullable=True)

# app/core/contracts/findings.py
facts: dict | None = None
```

`facts` is the structured extraction *behind* the quote — the same shape
`app/modules/crossref/facts.py` already produces for the contradiction engine (TS-217). **Reuse that
vocabulary rather than inventing a second one:**

```python
# canonical fact keys already established by crossref/facts.py
{
  "ld_rate_percent": 0.5,          # float, percent
  "ld_rate_period": "week",        # day|week|month
  "ld_cap_percent": 5.0,           # float or absent — ABSENT MEANS UNCAPPED, never 0
  "emd_percent": 2.0,
  "emd_amount_minor": 500000,      # minor units; distinct from emd_percent, never conflated
  "bid_validity_days": 120,
  "dlp_months": 12,
  "retention_percent": 5.0,
  "submission_datetime": "2026-08-01T15:00:00+05:30",
}
```

> **Critical semantic:** an absent `ld_cap_percent` means the LD clause is **uncapped**, which must
> produce **no loading** (`formulas.ld_exposure_cap` raises `MissingInputs`). Do not let a JSON
> default of `0` sneak in — that would silently price an unbounded exposure at zero, inverting the
> finding's meaning.

**Opportunity side** — in `app/modules/ingestion/models.py` (the module that owns `opportunities`):

```python
contract_value_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
contract_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
```

**Then simplify** `pricing/router.py`: drop `contract_value_minor`/`facts` query params, read from
the opportunity and the findings. Keep an explicit override path for what-if analysis, but the
default must be "use the persisted facts."

```python
@router.get("/opportunities/{opportunity_id}/loading")
def get_loading(
    opportunity_id: str,
    request: Request,
    contract_value_minor: int | None = None,   # optional override for what-if
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    # service resolves value from Opportunity when the override is absent,
    # and facts from each Finding.facts — raising PricingError("missing_contract_value")
    # rather than defaulting.
```

**Acceptance**
- A1. `risk` persists `facts` for a finding it extracted a rate/cap/period from.
- A2. `pricing.loading` computes a loading with **no** caller-supplied facts.
- A3. An opportunity with no `contract_value_minor` returns `409 missing_contract_value`, never a
  guessed value.
- A4. An uncapped LD finding still produces **no** loading (regression on the semantic above).

---

## TS-219 — Reproducibility chain (moat class 3, **P0**)

**Why.** Strategy §C.7. The product's accountability claim is that any finding can be re-derived.
Today nothing pins *what produced it*, so a rulepack or model change silently rewrites history.

**Change.** Add to `FindingRow` (and the `Finding` contract):

```python
rulepack_version: Mapped[str | None]  = mapped_column(String, nullable=True)
model_id:         Mapped[str | None]  = mapped_column(String, nullable=True)   # "none" for deterministic
prompt_hash:      Mapped[str | None]  = mapped_column(String(64), nullable=True)
document_hash:    Mapped[str | None]  = mapped_column(String(64), nullable=True)
engine_version:   Mapped[str | None]  = mapped_column(String, nullable=True)
```

Populate at the single choke point where a finding is created, not at each call site:

```python
# app/modules/findings/service.py (the store capability)
REPRO_FIELDS = ("rulepack_version", "model_id", "prompt_hash", "document_hash", "engine_version")

def store(self, workspace_id, opportunity_id, producer, findings, *, provenance: dict):
    """`provenance` carries the reproducibility chain for this whole run —
    identical for every finding a single pipeline invocation produces."""
    missing = [f for f in REPRO_FIELDS if not provenance.get(f)]
    if missing:
        # A deterministic producer must still pass model_id="none" explicitly.
        raise ValueError(f"incomplete reproducibility chain: {missing} (TS-219)")
    ...
```

`prompt_hash` = `sha256` of the fully-rendered prompt template **before** document text is injected
(so it identifies the prompt version, not the input). `document_hash` = the `sha256` the ingestion
store already computes. `engine_version` = the module version from its `ModuleSpec`.

**The acceptance gate is the hard part:** *deterministic stages byte-identical on re-run.*

```python
def test_deterministic_stages_are_byte_identical(...):
    run1 = run_pipeline(doc, classifier=NullClassifier())
    run2 = run_pipeline(doc, classifier=NullClassifier())
    # compare everything except row ids and timestamps
    assert canonical(run1) == canonical(run2)
```

`app/evalinvariants/checks.py` already has a determinism check (`check_determinism`) that takes an
optional rerun bundle — **wire this into it rather than writing a parallel mechanism.**

**Acceptance**
- A1. Every new finding carries a complete five-field chain; an incomplete one is rejected.
- A2. `model_id="none"` for deterministic producers (BOQ, deadlines) — never NULL, so "no model" and
  "forgot to record" stay distinguishable.
- A3. Two runs of the deterministic stages over the same document produce byte-identical findings
  modulo ids/timestamps.
- A4. A rulepack version bump changes `rulepack_version` on subsequently produced findings.

---

## Suggested commit sequence

```
feat(findings): TS-294/295/296 document_id, currency and facts on findings   [1 migration]
feat(risk,boq,qualification,standards): thread document_id/currency/facts through writers
feat(pricing): TS-296 source facts and contract value from persisted data
feat(evalinvariants): tighten quote and currency checks now that the columns exist
feat(findings): TS-219 reproducibility chain on every finding                [1 migration]
```
