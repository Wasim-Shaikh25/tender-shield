# Cross-Reference & Clause Diff — Spec

**Status:** implemented (TS-053 + TS-051 + TS-217)
**Requirement refs:** Phase 1.5 doc §5; `docs/TenderShield_Market_Strategy_2026.md` §C.5
**Task refs:** TS-053, TS-051, TS-217

## Purpose

Three related trust features that sit on top of the ingestion clause store:

1. **Clause Cross-Reference (TS-053):** search a topic/term across every document
   in an opportunity and get back ranked clause snippets with provenance.
2. **Clause Change Detection (TS-051):** compare two versions of a document
   (explicit `supersedes` chain or the two most recent uploads of the same kind)
   and report added, removed, and changed clauses.
3. **Contradiction Engine (TS-217, Strategy §C.5):** extract canonical facts
   (bid validity, EMD, submission datetime, LD rate, DLP, retention) from every
   clause in an opportunity, and flag when the *same* fact type disagrees
   across documents — naming the governing instance via a document-precedence
   order, without hiding either side's citation.

## Public interface

- **Capability published:** `crossref.service_factory`.
- **Capabilities consumed (soft):** `ingestion.service_factory`, `rulepacks.loader`.
- **Events:** none.
- **API routes** (prefix `/api/crossref`):
  - `GET /opportunities/{id}?q=<query>&limit=<n>` — ranked clause search.
  - `POST /opportunities/{id}/diff?document_id=<id>` — diff vs the superseded
    document; if omitted, compares the two latest documents of the same kind.
  - `GET /opportunities/{id}/contradictions` — fact-level cross-document
    contradictions, with the precedence order used and, for each
    contradiction, every instance's own citation plus the governing one.

## Data owned

None. Reads documents and clauses through `ingestion`.

## Behavior

- **B1 — Keyword search.** Query is tokenised into lowercase words. The DB returns
  a bounded candidate clause set (`limit * 10`, capped at 1000); each candidate is
  scored by token overlap against the query, normalised by the larger token set.
  Results include document filename/kind, clause ref, heading, page, and a
  300-char text preview. The `limit` parameter is clamped to 1–100 at the router.
- **B2 — Diff resolution.** If `document_id` is supplied, its `supersedes` column
  identifies the old version. Otherwise the service groups documents by `kind`
  and uses the two most recent uploads. If neither exists, it walks the
  opportunity's `supersedes` links.
- **B3 — Clause matching.** Clauses are keyed by `clause_ref` when present;
  unsegmented clauses use a synthetic positional key. A clause is `changed` when
  its normalised text differs from the old version; otherwise it is `added` or
  `removed`.
- **B4 — Org isolation.** All reads are scoped to the opportunity (and therefore
  to the org) by delegating to the ingestion service, which enforces its own
  org filter.
- **B5 — Canonical fact extraction (TS-217).** `app.modules.crossref.facts` is
  a **deterministic, regex-only** extractor over each clause's own stored
  text — no LLM, matching CLAUDE.md §4 ("numbers never come from the LLM").
  Six fact types: `bid_validity_days`, `emd_percent`, `emd_amount_minor`
  (kept separate from `emd_percent` — a percentage-of-cost figure and a flat
  currency amount are not the same quantity and must never be compared),
  `ld_rate_percent` (rate + period, e.g. `"0.5%/week"`), `dlp_months`,
  `retention_percent`, `submission_datetime` (parsed via Python's `date()`
  constructor — an impossible calendar date, e.g. 31 Feb, is silently
  skipped rather than guessed at). Every fact's `source_quote` is, by
  construction, a literal substring of the clause text it was extracted from.
- **B6 — Verification gate.** Before grouping, every extracted fact is
  re-verified: its `source_quote` must actually occur in its own clause's
  text (`app.modules.crossref.contradictions._verify`). This is a defensive
  invariant against extraction/storage corruption, not against LLM
  hallucination (there is no LLM in this path) — but the effect is the same
  guarantee the risk engine gives: nothing is shown without a citation that
  checks out (Strategy §C.5).
- **B7 — Grouping and disagreement.** Verified facts are grouped by
  `fact_type`. A type with more than one distinct value across its verified
  instances is a contradiction; a type where every instance agrees is not
  surfaced at all.
- **B8 — Document precedence names the governing instance.** The order is
  rulepack-configurable (`rulepacks/<pack>/document_precedence.yaml`,
  `RulePackLoader.document_precedence(pack_id, employer_family)`) and
  employer-family overridable; `in-works` ships the unvalidated default
  `[addendum, scc, gcc, nit]` (see that file for sourcing). rulepacks is a
  **soft dependency** — absent entirely, or shipping no
  `document_precedence.yaml`, both degrade to the hardcoded
  `crossref.contradictions.DEFAULT_PRECEDENCE` fallback, never a crash
  (CLAUDE.md §2). A document `kind` not present in the precedence order
  ranks lowest. When two or more instances tie at the top rank (e.g. two
  clauses in the same document type disagree with each other), the governing
  instance is deliberately left `None` with an `"ambiguous"` reason rather
  than guessing.
- **B9 — Both sides keep their citation.** The response always lists every
  instance (value, document, clause, page, quote) alongside the governing
  one — a contradiction is a decision aid, not a silent overwrite.

## Acceptance criteria

- A1: `GET /opportunities/{id}?q=payment&limit=20` returns up to 20 clauses
  containing "payment" ranked above unrelated clauses; `limit` > 100 is clamped.
- A2: Uploading a second version of a document and calling `POST /api/crossref/opportunities/{id}/diff` reports
  the added/removed/changed clauses.
- A3: Passing `document_id` of a document with `supersedes` set compares that
  specific pair.
- A4: Two documents stating the same bid-validity period produce no
  contradiction; stating different periods produces exactly one, with the
  higher-precedence document (e.g. an addendum over the GCC) named as
  governing and both instances' citations present.
- A5: Two instances of the same fact type tied at the same precedence rank
  (e.g. two conflicting statements within the same GCC) resolve to
  `governing: null` with an `"ambiguous"` reason, never a guess.
- A6: An employer-family precedence override changes which instance governs
  without changing which instances are reported.
- A7: A fact whose quote cannot be re-verified against its own clause text is
  dropped before grouping and can never itself create or resolve a
  contradiction.
- A8: With `rulepacks` disabled, or enabled with no `document_precedence.yaml`,
  the endpoint still returns contradictions using `DEFAULT_PRECEDENCE` — no crash.

## Out of scope

- Semantic similarity / embeddings (P2); paragraph-level diff (P2); automatic
  corrigendum ingestion (P2).
- Persisting contradictions into the shared Findings register — `Finding`
  has no `document_id` or `facts` field yet (tracked as TS-294/TS-295/TS-296);
  until those land, contradictions are served fresh via their own endpoint
  rather than forced into a shape that would lose the per-instance detail.
- Additional canonical fact types beyond the six named in Strategy §C.5, and
  non-regex (e.g. LLM-assisted) fact extraction — the whole point of this
  slice is that these particular six are cheap to get exactly right
  deterministically; anything fuzzier belongs in the risk-pattern engine.
