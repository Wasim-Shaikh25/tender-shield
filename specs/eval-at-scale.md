# Evaluation at Scale — 1,000+ Real Tenders, Automated — Spec

**Status:** draft
**Requirement refs:** `docs/TenderShield_Market_Strategy_2026.md` §A.2, §H.1; Build Doc §11.5, §19
**Task refs:** TS-224 – TS-233

## Purpose

Run the full TenderShield pipeline against **1,000+ real tender packs across multiple domains and
countries, unattended, on a server**, and produce a scored report — without requiring a human to
hand-annotate 1,000 gold answers.

The central problem this spec solves: **hand-labelling does not scale, but validation must.** The
answer is that most of what we need to know does not require a label. Four of the five scoring modes
below need zero human input; the fifth needs roughly 50 annotated tenders, not 1,000.

---

## 1. The scoring model — how we grade without labels

| Mode | Needs a human? | What it measures | Coverage |
|---|---|---|---|
| **M1 Structural invariants** | No | Correctness properties that must hold on *any* tender | 100% of corpus |
| **M2 Portal-metadata agreement** | No | Extraction accuracy against structured fields the portal already publishes | ~60–80% of corpus |
| **M3 Outcome backtest** | No | Predictive accuracy against real award records | Corpus with awards |
| **M4 Metamorphic consistency** | No | Robustness — same input in a different form must give the same answer | Sampled subset |
| **M5 Human gold set** | Yes (~50 tenders) | Judgment: severity calibration, noise, scope gaps, the loss-maker trap | 50 tenders |

### M1 — Structural invariants (the bulletproof test)

These assert properties that are true regardless of what the tender says. Every one is a hard
pass/fail, and any failure is a defect.

| Invariant | Assertion | Source |
|---|---|---|
| Quote integrity | Every `source_quote` appears **verbatim** in the cited document, ≤200 chars | `CLAUDE.md` §4; Build Doc §6.2 |
| Citation completeness | Every finding has `source_page` (or `[sheet:…]`) and a resolvable `document_id` | `CLAUDE.md` §4 |
| No invented numbers | Every number in a generated artifact traces to an extracted fact | Build Doc §6.5 |
| BOQ arithmetic closure | For every workbook: either line sums reconcile to stated totals, or a defect is reported. Never silently neither | Build Doc §6.4 |
| Determinism | Re-running the deterministic stages (BOQ, dates, severity) on the same input produces byte-identical output | Strategy §C.7 |
| Currency integrity | Every monetary value carries a currency and is in minor units | `CLAUDE.md` §4 |
| Tenant isolation | No finding references a `document_id` outside its own workspace | `CLAUDE.md` §4 |
| Graceful degradation | Unreadable pages are reported as unreadable, never silently dropped | Build Doc §12.4 |
| Budget | Per-review token count and wall-clock stay under configured ceilings | Strategy §G.3 |
| No crash | Pipeline completes or fails with a classified, actionable error | — |

**Target: 100% pass. Any M1 failure blocks release.** This is the single most valuable output of the
harness because it converts "we think it works" into "it satisfies N invariants on 1,000 real
documents."

### M2 — Portal-metadata agreement (free labels at scale)

Procurement portals publish structured metadata alongside the documents. That metadata **is** the
label for a large share of what we extract.

| Extracted fact | Portal field | Scoring |
|---|---|---|
| Submission deadline | `tenderPeriod.endDate` (OCDS) / CPPP closing datetime | Exact match to the minute |
| Tender value / estimated cost | `value.amount` | Exact match, currency-aware |
| EMD amount | EMD field where published | Exact match |
| Tender reference / ID | `ocid` / tender ID | Exact match |
| Employer / buyer | `buyer.name` | Normalized match |
| Bid validity | Where published | Exact match |

This yields **thousands of free labels** for deadline and value extraction — the two facts whose
correctness matters most in the first three minutes of the user experience.

Mismatches are triaged automatically into: `extraction_miss` (we found nothing),
`extraction_wrong` (we found a different value), `portal_wrong` (metadata contradicts the document —
happens, and is itself a finding worth surfacing to users).

### M3 — Outcome backtest

For corpus entries with award records, score predictions against reality. No labelling, standard
train/test discipline, out-of-sample only.

| Prediction | Ground truth | Metric |
|---|---|---|
| L1 award price | `awards[].value.amount` | MAE and MAPE vs estimate; calibration curve |
| Bidder count | Award record | MAE |
| Award latency | Award date − opening date | MAE in days |
| Retender likelihood | Subsequent tender with matching scope/employer | AUC |

Split by **time**, not randomly — train on awards before date *T*, test after — otherwise the
backtest leaks and the numbers are meaningless.

### M4 — Metamorphic consistency

Robustness properties that need no ground truth, only two runs:

- **Format invariance:** the same pack as native PDF vs rendered-to-image-and-OCR'd must produce the
  same finding set (allowing a configured tolerance on quote offsets).
- **Order invariance:** shuffling document upload order must not change findings.
- **Addendum monotonicity:** applying an addendum must change only findings traceable to the changed
  clauses.
- **Redundancy invariance:** uploading the same document twice must not double the findings.
- **Locale invariance:** the same clause in EN and AR/HI must yield the same categorised finding
  (GCC/India packs).

These catch fragility that accuracy metrics hide, and they are cheap.

### M5 — Human gold set (~50 tenders)

The irreducible part (Build Doc §14.2). Deliberately small and composed for coverage, not volume:

| Slice | Count | Why |
|---|---|---|
| Known loss-makers (contractor-supplied) | 5 | The only source for "did it catch the trap that bit" |
| Government works — CPWD / state PWD | 15 | Primary employer family |
| NHAI / railways | 5 | Different standard forms |
| Private developer | 5 | Different risk calibration (Strategy §A, Build Doc §14.2) |
| Scanned / poor-quality | 5 | OCR degradation honesty |
| MEP / mechanical / supply-and-erection | 10 | Domain-agnosticism proof |
| Saudi (Etimad) / GCC FIDIC | 5 | Pack transfer proof |

Gold answers are authored per Build Doc §19 and stored under `evals/in-works/<slice>/`.

---

## 2. Corpus acquisition

### 2.1 Normalization target — OCDS

Every source is mapped into **OCDS-shaped records** ([Open Contracting Data Standard](https://standard.open-contracting.org/latest/en/primer/what/),
implemented by 30+ governments). This is what makes the harness country-agnostic: adapters differ,
the corpus schema does not.

```
CorpusTender:
  ocid, source_id, country, jurisdiction, buyer{name, family, division}
  classification{cpv|nic|custom}, value{amount_minor, currency}
  tender_period{start, end}, documents[{url, kind, sha256, bytes, mime}]
  raw_metadata            # source-native fields, preserved verbatim
CorpusAward:
  ocid, date, suppliers[], value{amount_minor, currency}, bidder_count, status
```

**Implemented (TS-224)** in `backend/app/evalcorpus/models.py` as dataclasses:
`CorpusTender`, `CorpusDocument`, `CorpusAward`, `Buyer`, `Provenance`.

Money follows `CLAUDE.md` §4 — OCDS quotes `value.amount` in major units as a decimal, so
`to_minor_units()` converts exactly once at the boundary, with a per-currency exponent table
(0 for JPY/KRW, 3 for KWD/BHD/OMR, 2 otherwise). A missing amount maps to `None`, never `0`:
"no value published" and "worth nothing" are different facts.

`CorpusTender.document_set_hash` counts only *fetched* documents, so a partially harvested
tender cannot masquerade as a complete one in the runner's cache key.

### 2.2 Source adapters

Each adapter is a self-contained plugin implementing `fetch_index()`, `fetch_documents()`
and `fetch_awards()`, and declaring an `AdapterInfo` that records its **legality review**
(terms of use, whether an official API exists, published rate limit). The review travels
with the code — an adapter without one does not ship.
**Legality is reviewed per source before an adapter ships**, and the finding is recorded in the
adapter docstring (terms of use, robots.txt, rate limits, whether an official API exists).

| Adapter | Country | Access | Priority |
|---|---|---|---|
| `cppp` | India | Archive search + document download | P0 |
| `state_nic` (parameterised per state) | India | NIC eProcurement instances | P0 |
| `nhai` | India | Free document download | P1 |
| `gem` | India | Portal | P2 |
| `etimad` | Saudi | [Official API — Tenders Inquiry Service](https://apiportal.etimad.sa/en/api_products/TendersInquiryService) | P1 |
| `ocds_registry` | 30+ countries | [OCP Data Registry bulk JSON](https://data.open-contracting.org/en/search/) | P1 |
| `ted` | EU | [TED API + SPARQL + eForms XML](https://developer.ted.europa.eu/home) | P2 |
| `uk_cf` | UK | Contracts Finder JSON/OCDS | P2 |
| `worldbank` / `adb` | MDB | Public SBDs and feeds | P2 |
| `ocds-file` | * | **Implemented (TS-224)** — local OCDS release packages, bare release arrays, single releases, or `.jsonl`. This is the reference implementation of the contract and the offline path used by tests and CI; an OCP Data Registry bulk download is this adapter pointed at the unpacked archive | done |

### 2.3 Harvest rules (non-negotiable)

- **Respect `robots.txt`, published rate limits, and terms of use.** An adapter that cannot comply is
  not shipped.
- **Polite by default:** configurable delay, single concurrent connection per host unless an official
  API permits more, identifying User-Agent with contact details.
- **Never harvest behind authentication** or paywalls, and never use a bidder account to download
  documents the public cannot access.
- **Public records only.** Customer-supplied documents never enter the corpus
  (`evals/in-works/README.md`).
- Store by `sha256`; re-download only on change. Full provenance (`source_url`, `fetched_at`,
  `http_status`) retained per document.

> ⚠️ CPPP returned HTTP 403 to a datacenter IP during research. Harvesting will likely need an
> allowed egress path. Resolve this legitimately — an official data request or a compliant
> egress — never by evading a block.

---

## 3. Runner architecture

```
scripts/corpus_harvest.py        # CLI: adapters → normalized corpus + manifest   [TS-224 ✅]
scripts/bulk_eval.py             # orchestrator → per-tender runs → results.jsonl [TS-230]
scripts/eval_report.py           # results.jsonl → scorecard.md + regression diff  [TS-231]
backend/app/evalcorpus/          # corpus schema, adapters, store, harvest         [TS-224 ✅]
backend/app/modules/evalrunner/  # optional in-app runner (Celery tasks, admin UI) [TS-230]
```

> The corpus logic lives in `backend/app/evalcorpus/` rather than in `scripts/` so it is
> typed, linted and covered by the normal test suite; the script is a thin CLI over it. The
> package sits outside `app/modules/` deliberately — it is offline evaluation infrastructure,
> not a product feature, and nothing in the request path imports it.

**Corpus storage (TS-224).** Documents are content-addressed by `sha256` with two-level
directory fan-out, so the same CPWD GCC appearing in a thousand tenders costs one blob.
Manifests are JSONL — appendable, greppable and diffable between runs. Every manifest line
carries a marker that source adapters skip, so a corpus stored inside a scanned source
directory can never be re-ingested as input (a real defect caught by the TS-224 tests, since
a `CorpusTender` record carries an `ocid` and is otherwise shaped exactly like a release).

Harvested corpora are git-ignored (`evals/corpus/`, `evals/runs/`): public records, but
large and reproducible from source.

### 3.1 Execution model

- **Work queue:** Celery (already in the stack — `app/core/celery.py`), one task per tender, so a
  1,000-tender run is 1,000 independent units.
- **Isolation:** each run executes in a disposable workspace, torn down after, so tenant-isolation
  invariants (M1) are exercised for real.
- **Resumability:** checkpoint per tender keyed by `(run_id, ocid, document_set_hash)`. Re-running a
  run resumes; it never re-does completed units.
- **Idempotency:** identical `document_set_hash` + identical `rulepack_version` + identical
  `model_id` returns the cached result unless `--force`.
- **Sharding:** `--shard i/n` for horizontal scale-out.
- **Cost guard:** hard token and wall-clock budget per run with a kill switch; the run aborts
  cleanly and reports partial results rather than silently spending.
- **Failure classification:** every failure is tagged (`ocr_failed`, `parse_failed`, `timeout`,
  `llm_error`, `invariant_violation`) so the report is actionable rather than a pile of tracebacks.

### 3.2 Output

```
evals/runs/<run_id>/
  manifest.json        # corpus slice, rulepack_version, model_id, engine_version, git sha
  results.jsonl        # one record per tender: findings, timings, tokens, invariant results
  scorecard.md         # M1–M5 rollup, human-readable
  regressions.md       # diff vs the previous run on the same corpus slice
  failures/            # per-tender artifacts for anything that failed
```

### 3.3 Metrics emitted

| Metric | Bar |
|---|---|
| M1 structural pass rate | **100%** — any failure blocks release |
| Quote-verbatim rate | **100%** |
| Deadline exact-match vs portal metadata | ≥ 95% |
| Tender value match | ≥ 95% |
| Findings per tender (distribution) | Noise proxy; investigate tails |
| Crash / timeout rate | < 1% |
| OCR fallback rate | Tracked by country and format |
| p50 / p95 wall-clock per tender | Against Build Doc §1.3 NFRs |
| Fully-loaded cost per review (p50/p95) | Strategy §G.2 |
| L1 backtest MAPE | Baseline first, then improve |
| Gold-set recall / critical recall / noise | Build Doc §19.5 bars |

### 3.4 CI integration

- **Per-PR:** 20-tender smoke slice, M1 + M4 only. Must be green to merge.
- **Nightly:** 100-tender slice, M1 + M2 + M4, regression diff vs previous night.
- **Weekly:** full 1,000+ corpus, all modes, published scorecard.
- **Gate:** a >2pt drop on any headline metric blocks the rulepack or prompt change that caused it
  (Build Doc §11.5).

---

## 4. Data owned

New tables, owned by the eval runner, **outside** the tenant data model:

- `corpus_tenders`, `corpus_documents`, `corpus_awards` — the harvested corpus
- `eval_runs`, `eval_results` — run manifests and per-tender outcomes

These are **not** workspace-scoped and must not be reachable from any tenant-facing route. The
runner is admin-only.

## 5. Acceptance criteria

1. `scripts/corpus_harvest.py --source cppp --limit 100` produces ≥100 normalized `CorpusTender`
   records with documents stored by sha256 and full provenance.
2. Adapters exist and are legality-reviewed for at least: CPPP, one state NIC portal, Etimad, OCDS
   registry.
3. `scripts/bulk_eval.py --corpus <slice> --shard 0/1` runs unattended to completion on ≥1,000
   tenders, resumable after a kill, with a working cost guard.
4. M1 invariants are asserted on every tender; the run fails loudly if any invariant is violated.
5. M2 agreement is computed wherever portal metadata exists.
6. M3 backtest runs with a time-based split on the award subset.
7. M4 metamorphic checks run on a sampled subset each run.
8. `evals/runs/<run_id>/scorecard.md` is generated automatically and is readable without the raw data.
9. Regression diff against the previous run on the same slice is produced automatically.
10. CI runs the smoke slice per PR and blocks on M1 failure.
11. No customer document ever enters the corpus; no authenticated or paywalled source is harvested.

## 6. Out of scope

- Bidding, bid submission, or any interaction with a live tender
- Harvesting behind authentication, paywalls, or a bidder account
- Publishing harvested documents; the corpus is internal evaluation infrastructure only
- Replacing the human gold set — M1–M4 measure correctness and robustness, not judgment
