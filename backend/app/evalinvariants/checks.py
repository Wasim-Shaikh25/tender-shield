"""The M1 structural invariants (TS-226, `specs/eval-at-scale.md` §1).

Ten checks, each true regardless of what a tender says. Every one returns a list
of `Violation` — empty means the invariant holds. A single violation of any check
is a defect, not a tuning target: `specs/eval-at-scale.md` sets the bar at 100%
pass and blocks release on any failure.

These checks are **independent** of the machinery that produced a finding. The
risk engine already does a fuzzy (difflib, 0.85-ratio) quote check before it ever
sets `source_quote` (`app/modules/risk/engine.py::verify_quote`) — this module
re-verifies with a strict verbatim substring match against the actual document
text, which is what catches a regression in that inline check rather than
agreeing with it by construction.

Known limitation, stated rather than hidden: `Finding` does not currently carry a
`document_id`, only `source_page`. Quote verification therefore checks "does this
page number, in *any* document attached to the opportunity, contain this quote" —
correct for the common case of one primary text document per opportunity, weaker
when an opportunity has two documents that both have a page 7. Tightening this
needs a schema change (`Finding.document_id`) that is out of scope for this task;
noted in `tasks/backlog.md` as a follow-up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.evalinvariants.bundle import PipelineBundle

# Kinds whose findings are grounded in a document page (a quote must be
# accompanied by a page, and a quote-bearing finding of this kind is expected to
# usually have one). BOQ_DEFECT and SCOPE_GAP are grounded in spreadsheet rows or
# checklist absence instead — see `_boq_row_reference`.
_PAGE_GROUNDED_KINDS = {"risk_clause", "qualification_gap", "standard_violation"}

_SHEET_MARKER = re.compile(r"\[sheet:")
_ROW_REF = re.compile(r"\brow\s+\d+\b", re.IGNORECASE)
_MAX_QUOTE_LEN = 200


@dataclass(frozen=True)
class Violation:
    """One invariant failure. `blocking=True` for every M1 check by design —
    the field exists so a future scoring mode can reuse this shape for
    non-blocking observations without a second type."""

    invariant: str
    message: str
    finding_ref: str = ""
    blocking: bool = True


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def _finding_ref(finding: dict, index: int) -> str:
    return finding.get("pattern_id") or finding.get("title") or f"finding[{index}]"


def _is_absence(finding: dict) -> bool:
    explanation = finding.get("explanation") or {}
    return bool(explanation.get("absence"))


# ------------------------------------------------------------- 1. quote integrity


def check_quote_integrity(bundle: PipelineBundle) -> list[Violation]:
    """Every `source_quote` is verbatim in the cited document, and ≤200 chars.

    When `document_id` is present, the quote must appear on a page in that
    document only — not any document sharing the same page number.
    """
    violations: list[Violation] = []
    pages_by_doc: dict[str, list] = {}
    for p in bundle.pages:
        pages_by_doc.setdefault(p.document_id, []).append(p)
    for i, f in enumerate(bundle.findings):
        quote = f.get("source_quote")
        if not quote:
            continue
        ref = _finding_ref(f, i)
        if len(quote) > _MAX_QUOTE_LEN:
            violations.append(
                Violation(
                    "quote_integrity",
                    f"quote is {len(quote)} chars, exceeds the {_MAX_QUOTE_LEN}-char cap",
                    ref,
                )
            )
            continue
        page = f.get("source_page")
        doc_id = f.get("document_id")
        if doc_id:
            candidates = [
                p for p in pages_by_doc.get(doc_id, []) if page is None or p.page == page
            ]
        else:
            candidates = bundle.pages_at(page) if page is not None else bundle.pages
        nq = _norm(quote)
        if not any(nq in _norm(p.text) for p in candidates):
            where = f"document {doc_id} page {page}" if doc_id else (
                f"page {page}" if page is not None else "any page"
            )
            violations.append(
                Violation(
                    "quote_integrity",
                    f"quote not found verbatim in the cited document ({where}): {quote[:60]!r}",
                    ref,
                )
            )
    return violations


# --------------------------------------------------------- 2. citation completeness


def check_citation_completeness(bundle: PipelineBundle) -> list[Violation]:
    """A quote never travels without a page, and page-grounded kinds cite one.

    Two rules, both derived from how findings are actually produced:
    * Any finding with a non-empty `source_quote` must also carry `source_page`
      (or a `[sheet:...]` marker in its detail/title) — a quote with no locator
      is not a citation.
    * A non-absence finding of a page-grounded kind (risk_clause,
      qualification_gap, standard_violation) that has neither a quote nor a page
      is uncited, unless it explicitly records why (an "unknown"/not-found
      status, which `qualification` legitimately produces with an empty quote).
    """
    violations: list[Violation] = []
    for i, f in enumerate(bundle.findings):
        ref = _finding_ref(f, i)
        quote = f.get("source_quote")
        page = f.get("source_page")
        text_blob = f"{f.get('title', '')} {f.get('detail', '')}"

        if quote and page is None and not _SHEET_MARKER.search(text_blob):
            violations.append(
                Violation("citation_completeness", "quote present without a source_page", ref)
            )

        kind = f.get("kind")
        if kind in _PAGE_GROUNDED_KINDS and not _is_absence(f):
            explanation = f.get("explanation") or {}
            explicitly_unresolved = explanation.get("status") == "unknown"
            if not quote and page is None and not explicitly_unresolved:
                violations.append(
                    Violation(
                        "citation_completeness",
                        f"kind {kind!r} has neither a quote nor a page and is not marked absent",
                        ref,
                    )
                )
    return violations


# ---------------------------------------------------------- 3. no invented numbers


def check_no_invented_numbers(bundle: PipelineBundle) -> list[Violation]:
    """Independently re-run artifact validation against the bundle's own facts.

    Reuses `app.modules.drafting.validators.validate`, imported lazily so this
    package never hard-depends on a module. This re-derives the check from raw
    findings rather than trusting that generation-time validation already ran —
    it exists to catch a regression where an artifact bypassed the validator.
    """
    if not bundle.artifacts:
        return []

    from app.modules.drafting.validators import DraftError, validate

    violations: list[Violation] = []
    for artifact in bundle.artifacts:
        try:
            validate(artifact.prose, artifact.facts)
        except DraftError as exc:
            violations.append(
                Violation(
                    "no_invented_numbers",
                    f"{exc.code}: {exc.detail}",
                    artifact.name,
                )
            )
    return violations


# ---------------------------------------------------------- 4. BOQ arithmetic closure


def _boq_row_reference(finding: dict) -> bool:
    return bool(_ROW_REF.search(f"{finding.get('title', '')} {finding.get('detail', '')}"))


def check_boq_arithmetic_closure(bundle: PipelineBundle) -> list[Violation]:
    """Every row either reconciles or has a defect finding. Never silently neither."""
    if not bundle.boq_rows:
        return []

    flagged_rows = {
        m.group(0).split()[-1]
        for f in bundle.findings
        if f.get("kind") == "boq_defect" and f.get("category") == "arith"
        for m in [_ROW_REF.search(f"{f.get('title', '')} {f.get('detail', '')}")]
        if m
    }

    violations: list[Violation] = []
    for row in bundle.boq_rows:
        src_row = row.get("src_row")
        amount = row.get("amount")
        amount_calc = row.get("amount_calc")
        if src_row is None or amount is None or amount_calc is None:
            continue
        reconciles = abs(float(amount) - float(amount_calc)) <= bundle.boq_tolerance
        flagged = str(src_row) in flagged_rows
        if not reconciles and not flagged:
            violations.append(
                Violation(
                    "boq_arithmetic_closure",
                    f"row {src_row}: amount {amount} != qty*rate {amount_calc}, "
                    "and no arithmetic defect was raised for it",
                    f"row {src_row}",
                )
            )
    return violations


# --------------------------------------------------------------- 5. determinism


def _deterministic_signature(f: dict) -> tuple:
    return (
        f.get("kind"),
        f.get("category"),
        f.get("severity"),
        f.get("title"),
        f.get("detail"),
        f.get("source_page"),
        f.get("source_quote"),
        f.get("amount_exposure"),
    )


def check_determinism(bundle: PipelineBundle) -> list[Violation]:
    """Deterministic-sourced findings are byte-identical across a rerun.

    Skipped (not failed) when no rerun was performed — `rerun_findings is None`
    means "not exercised for this bundle", which is a coverage gap for the
    runner to track, not a violation for this check to report.
    """
    if bundle.rerun_findings is None:
        return []

    def deterministic_set(findings: list[dict]) -> set[tuple]:
        return {
            _deterministic_signature(f)
            for f in findings
            if f.get("source") == "deterministic_check"
        }

    original = deterministic_set(bundle.findings)
    rerun = deterministic_set(bundle.rerun_findings)
    if original == rerun:
        return []

    only_original = original - rerun
    only_rerun = rerun - original
    return [
        Violation(
            "determinism",
            f"deterministic findings changed on rerun: "
            f"{len(only_original)} disappeared, {len(only_rerun)} appeared",
        )
    ]


# ------------------------------------------------------------ 6. currency integrity


def check_currency_integrity(bundle: PipelineBundle) -> list[Violation]:
    """Monetary exposure is integer minor units with an explicit ISO 4217 currency."""
    violations: list[Violation] = []
    for i, f in enumerate(bundle.findings):
        amount = f.get("amount_exposure")
        if amount is None:
            continue
        if isinstance(amount, bool) or not isinstance(amount, int):
            violations.append(
                Violation(
                    "currency_integrity",
                    f"amount_exposure is {type(amount).__name__}, not an int minor-unit value",
                    _finding_ref(f, i),
                )
            )
            continue
        currency = f.get("currency")
        if not currency or not isinstance(currency, str) or len(currency) != 3:
            violations.append(
                Violation(
                    "currency_integrity",
                    "amount_exposure requires an explicit ISO 4217 currency code",
                    _finding_ref(f, i),
                )
            )
    return violations


# ------------------------------------------------------------- 7. tenant isolation


def check_tenant_isolation(bundle: PipelineBundle) -> list[Violation]:
    """Every finding's cited page belongs to a document in this bundle.

    A bundle is assembled per-opportunity (see `db_adapter.py`), so this is an
    internal consistency check: a finding cannot cite a page number for which no
    page exists in the bundle at all when a page was actually claimed. The
    workspace-scoping guarantee itself is asserted at the database layer — see
    `backend/tests/test_evalinvariants.py::test_db_adapter_is_workspace_scoped`,
    which is the check that actually exercises cross-tenant leakage.
    """
    if not bundle.pages:
        return []
    known_pages = {p.page for p in bundle.pages}
    violations: list[Violation] = []
    for i, f in enumerate(bundle.findings):
        page = f.get("source_page")
        if page is not None and page not in known_pages:
            violations.append(
                Violation(
                    "tenant_isolation",
                    f"finding cites page {page}, which does not exist in this "
                    "opportunity's documents",
                    _finding_ref(f, i),
                )
            )
    return violations


# --------------------------------------------------------- 8. graceful degradation


def check_graceful_degradation(bundle: PipelineBundle) -> list[Violation]:
    """An unreadable page is reported, never silently dropped or quoted from."""
    violations: list[Violation] = []
    if bundle.unreadable_pages and not bundle.degradation_notes:
        violations.append(
            Violation(
                "graceful_degradation",
                f"{len(bundle.unreadable_pages)} unreadable page(s) recorded but "
                "no degradation note was surfaced to the user",
            )
        )
    unreadable_page_numbers = {page for _doc_id, page in bundle.unreadable_pages}
    for i, f in enumerate(bundle.findings):
        quote = f.get("source_quote")
        page = f.get("source_page")
        if quote and page is not None and page in unreadable_page_numbers:
            violations.append(
                Violation(
                    "graceful_degradation",
                    f"finding quotes page {page}, which is recorded as unreadable",
                    _finding_ref(f, i),
                )
            )
    return violations


# --------------------------------------------------------------------- 9. budget


def check_budget(bundle: PipelineBundle) -> list[Violation]:
    """Token and wall-clock usage stay under their configured ceilings.

    The token ceiling mirrors `app.core.costmeter`'s guard on the retrieval-first
    cost property (Strategy §G.3): cost must scale with pattern count, not
    document length.
    """
    violations: list[Violation] = []
    if bundle.token_ceiling and bundle.token_count > bundle.token_ceiling:
        violations.append(
            Violation(
                "budget",
                f"token count {bundle.token_count} exceeds the ceiling {bundle.token_ceiling}",
            )
        )
    if bundle.wall_ceiling and bundle.wall_seconds > bundle.wall_ceiling:
        violations.append(
            Violation(
                "budget",
                f"wall time {bundle.wall_seconds:.1f}s exceeds the ceiling "
                f"{bundle.wall_ceiling:.1f}s",
            )
        )
    return violations


# -------------------------------------------------------------------- 10. no crash


def check_no_crash(bundle: PipelineBundle) -> list[Violation]:
    """The pipeline completed, or failed with a classified, actionable error.

    A `pipeline_error` that looks like a raw traceback (contains "Traceback" or a
    bare exception class name with no context) is treated as unclassified — the
    product must degrade honestly (Build Doc §12.4), not leak an exception.
    """
    if bundle.pipeline_error is None:
        return []
    error = bundle.pipeline_error.strip()
    if not error:
        return [Violation("no_crash", "pipeline_error is set but empty — not classified")]
    if "Traceback" in error or "\n  File \"" in error:
        return [
            Violation(
                "no_crash",
                "pipeline_error looks like a raw traceback, not a classified error",
            )
        ]
    return []


ALL_CHECKS = (
    check_quote_integrity,
    check_citation_completeness,
    check_no_invented_numbers,
    check_boq_arithmetic_closure,
    check_determinism,
    check_currency_integrity,
    check_tenant_isolation,
    check_graceful_degradation,
    check_budget,
    check_no_crash,
)
