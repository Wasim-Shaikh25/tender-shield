"""Tests for the M1 structural invariant suite (TS-226).

Each check gets two kinds of test: a legitimate case that must pass (proving the
check doesn't false-positive on real pipeline output shapes) and a violating case
that must fail (proving the check actually catches the defect it claims to). The
legitimate fixtures are drawn from how `risk`, `boq` and `qualification` actually
build findings today, not idealized shapes.
"""

from __future__ import annotations

import uuid

import pandas as pd
import pytest

import app.modules.auth.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base, make_engine, make_session_factory
from app.evalinvariants import (
    Artifact,
    DocPage,
    PipelineBundle,
    bundle_from_opportunity,
    run_m1,
)
from app.evalinvariants.checks import (
    check_boq_arithmetic_closure,
    check_budget,
    check_citation_completeness,
    check_currency_integrity,
    check_determinism,
    check_graceful_degradation,
    check_no_crash,
    check_no_invented_numbers,
    check_quote_integrity,
    check_tenant_isolation,
)
from app.modules.boq.engine import normalize, run_checks
from app.modules.findings.models import FindingRow  # noqa: F401
from app.modules.findings.store import FindingStore
from app.modules.risk.engine import run_pattern
from app.modules.rulepacks.loader import RulePackLoader


def _finding(**overrides) -> dict:
    base = {
        "kind": "risk_clause",
        "category": "payment",
        "severity": "high",
        "title": "Extended payment period",
        "detail": "Payment within 120 days.",
        "source": "ai_suggestion",
        "source_page": 3,
        "source_quote": "payment shall be released within 120 days",
        "amount_exposure": None,
        "explanation": {"absence": False},
    }
    base.update(overrides)
    return base


def _page(page: int, text: str, document_id: str = "doc-1") -> DocPage:
    return DocPage(document_id=document_id, page=page, text=text)


# ------------------------------------------------------------- 1. quote integrity


def test_quote_integrity_passes_when_quote_is_verbatim():
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        pages=[_page(3, "... payment shall be released within 120 days of RA bill ...")],
        findings=[_finding()],
    )
    assert check_quote_integrity(bundle) == []


def test_quote_integrity_fails_when_quote_is_not_in_the_document():
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        pages=[_page(3, "completely unrelated clause text")],
        findings=[_finding()],
    )
    violations = check_quote_integrity(bundle)
    assert len(violations) == 1
    assert violations[0].invariant == "quote_integrity"


def test_quote_integrity_is_case_and_whitespace_insensitive():
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        pages=[_page(3, "PAYMENT   SHALL BE released \n within 120 days")],
        findings=[_finding()],
    )
    assert check_quote_integrity(bundle) == []


def test_quote_integrity_rejects_quotes_over_200_chars():
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        pages=[_page(3, "x" * 300)],
        findings=[_finding(source_quote="x" * 201)],
    )
    violations = check_quote_integrity(bundle)
    assert any("200-char" in v.message for v in violations)


def test_quote_integrity_checks_only_the_cited_page():
    """A quote that exists on the wrong page is still a violation."""
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        pages=[_page(9, "payment shall be released within 120 days")],
        findings=[_finding(source_page=3)],  # quote lives on page 9, cited as page 3
    )
    assert len(check_quote_integrity(bundle)) == 1


def test_quote_integrity_skips_findings_without_a_quote():
    bundle = PipelineBundle(
        opportunity_id="o", workspace_id="w", pages=[], findings=[_finding(source_quote=None)]
    )
    assert check_quote_integrity(bundle) == []


# --------------------------------------------------------- 2. citation completeness


def test_citation_completeness_passes_for_a_normal_risk_finding():
    bundle = PipelineBundle(opportunity_id="o", workspace_id="w", findings=[_finding()])
    assert check_citation_completeness(bundle) == []


def test_citation_completeness_fails_when_quote_has_no_page():
    bundle = PipelineBundle(
        opportunity_id="o", workspace_id="w", findings=[_finding(source_page=None)]
    )
    violations = check_citation_completeness(bundle)
    assert any("without a source_page" in v.message for v in violations)


def test_citation_completeness_accepts_a_sheet_marker_in_place_of_a_page():
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        findings=[
            _finding(
                source_page=None, detail="[sheet:BOQ] payment shall be released within 120 days"
            )
        ],
    )
    assert check_citation_completeness(bundle) == []


def test_citation_completeness_passes_for_an_absence_finding_with_no_evidence():
    """Absence findings (risk/engine.py::_absence_finding) legitimately have
    neither a quote nor a page — the absence itself is the finding."""
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        findings=[
            _finding(
                source_page=None,
                source_quote=None,
                title="Escalation — clause appears ABSENT",
                explanation={"absence": True},
            )
        ],
    )
    assert check_citation_completeness(bundle) == []


def test_citation_completeness_passes_for_qualification_unknown_status():
    """qualification/service.py legitimately produces empty evidence for an
    'unknown' (not found) criterion."""
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        findings=[
            _finding(
                kind="qualification_gap",
                source_page=None,
                source_quote="",
                explanation={"status": "unknown", "key": "turnover"},
            )
        ],
    )
    assert check_citation_completeness(bundle) == []


def test_citation_completeness_fails_for_uncited_non_absence_risk_finding():
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        findings=[
            _finding(
                source_page=None,
                source_quote=None,
                explanation={"absence": False},
            )
        ],
    )
    violations = check_citation_completeness(bundle)
    assert any("neither a quote nor a page" in v.message for v in violations)


def test_citation_completeness_does_not_require_a_page_for_boq_defects():
    """BOQ defects cite a spreadsheet row (in the title), not a document page."""
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        findings=[
            _finding(
                kind="boq_defect",
                category="arith",
                source_page=None,
                source_quote=None,
                title="Arithmetic error at row 3 (X: concrete work)",
            )
        ],
    )
    assert check_citation_completeness(bundle) == []


# ---------------------------------------------------------- 3. no invented numbers


class _FakeFacts:
    def __init__(self, quotes=(), amounts=(), clause_refs=()):
        self._quotes = [q.lower() for q in quotes]
        self._amounts = list(amounts)
        self.clause_refs = set(clause_refs)

    def has_quote(self, q):
        return q.lower() in self._quotes

    def has_amount(self, value, tol=50):
        return any(abs(value - a) <= tol for a in self._amounts)


def test_no_invented_numbers_passes_for_grounded_prose():
    artifact = Artifact(
        name="clarification-letter",
        prose='Clause GCC 10.1 states "payment within 120 days".',
        facts=_FakeFacts(quotes=["payment within 120 days"], clause_refs={"GCC 10.1"}),
    )
    bundle = PipelineBundle(opportunity_id="o", workspace_id="w", artifacts=[artifact])
    assert check_no_invented_numbers(bundle) == []


def test_no_invented_numbers_fails_for_an_invented_quote():
    artifact = Artifact(
        name="clarification-letter",
        prose='The clause states "this exact text was never extracted".',
        facts=_FakeFacts(quotes=[]),
    )
    bundle = PipelineBundle(opportunity_id="o", workspace_id="w", artifacts=[artifact])
    violations = check_no_invented_numbers(bundle)
    assert len(violations) == 1
    assert violations[0].invariant == "no_invented_numbers"


def test_no_invented_numbers_fails_for_an_uncited_clause_reference():
    artifact = Artifact(
        name="letter", prose="Per Clause 14.2, this applies.", facts=_FakeFacts()
    )
    bundle = PipelineBundle(opportunity_id="o", workspace_id="w", artifacts=[artifact])
    assert len(check_no_invented_numbers(bundle)) == 1


def test_no_invented_numbers_skips_bundles_with_no_artifacts():
    bundle = PipelineBundle(opportunity_id="o", workspace_id="w")
    assert check_no_invented_numbers(bundle) == []


# ------------------------------------------------------- 4. BOQ arithmetic closure


def test_boq_closure_passes_when_reconciling_rows_have_no_defect():
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        boq_rows=[{"src_row": 1, "amount": 1000.0, "amount_calc": 1000.0}],
        boq_tolerance=1.0,
    )
    assert check_boq_arithmetic_closure(bundle) == []


def test_boq_closure_passes_when_a_mismatch_has_a_defect_finding():
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        boq_rows=[{"src_row": 3, "amount": 1000.0, "amount_calc": 1144000.0}],
        findings=[
            {
                "kind": "boq_defect",
                "category": "arith",
                "title": "Arithmetic error at row 3 (X)",
                "detail": "amount 1000.00 != qty*rate 1144000.00",
            }
        ],
    )
    assert check_boq_arithmetic_closure(bundle) == []


def test_boq_closure_fails_when_a_mismatch_has_no_defect_finding():
    """This is the invariant's whole point: never silently neither."""
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        boq_rows=[{"src_row": 3, "amount": 1000.0, "amount_calc": 1144000.0}],
        findings=[],
    )
    violations = check_boq_arithmetic_closure(bundle)
    assert len(violations) == 1
    assert "row 3" in violations[0].message


def test_boq_closure_is_skipped_when_no_boq_rows_present():
    bundle = PipelineBundle(opportunity_id="o", workspace_id="w")
    assert check_boq_arithmetic_closure(bundle) == []


# ---------------------------------------------------------------- 5. determinism


def test_determinism_not_exercised_without_a_rerun():
    bundle = PipelineBundle(opportunity_id="o", workspace_id="w", findings=[_finding()])
    assert check_determinism(bundle) == []


def test_determinism_passes_when_rerun_matches():
    f = _finding(source="deterministic_check")
    bundle = PipelineBundle(
        opportunity_id="o", workspace_id="w", findings=[f], rerun_findings=[dict(f)]
    )
    assert check_determinism(bundle) == []


def test_determinism_fails_when_rerun_differs():
    f = _finding(source="deterministic_check")
    changed = dict(f, severity="low")
    bundle = PipelineBundle(
        opportunity_id="o", workspace_id="w", findings=[f], rerun_findings=[changed]
    )
    violations = check_determinism(bundle)
    assert len(violations) == 1
    assert violations[0].invariant == "determinism"


def test_determinism_ignores_non_deterministic_findings():
    """An AI-sourced finding is allowed to differ between runs; only
    deterministic_check findings must be byte-identical."""
    f = _finding(source="ai_suggestion")
    changed = dict(f, severity="low")
    bundle = PipelineBundle(
        opportunity_id="o", workspace_id="w", findings=[f], rerun_findings=[changed]
    )
    assert check_determinism(bundle) == []


# ------------------------------------------------------------ 6. currency integrity


def test_currency_integrity_passes_for_an_int_amount():
    bundle = PipelineBundle(
        opportunity_id="o", workspace_id="w", findings=[_finding(amount_exposure=1_500_000)]
    )
    assert check_currency_integrity(bundle) == []


def test_currency_integrity_fails_for_a_float_amount():
    bundle = PipelineBundle(
        opportunity_id="o", workspace_id="w", findings=[_finding(amount_exposure=15000.50)]
    )
    violations = check_currency_integrity(bundle)
    assert len(violations) == 1
    assert violations[0].invariant == "currency_integrity"


def test_currency_integrity_skips_findings_without_an_amount():
    bundle = PipelineBundle(
        opportunity_id="o", workspace_id="w", findings=[_finding(amount_exposure=None)]
    )
    assert check_currency_integrity(bundle) == []


# ------------------------------------------------------------- 7. tenant isolation


def test_tenant_isolation_passes_when_pages_match():
    bundle = PipelineBundle(
        opportunity_id="o", workspace_id="w", pages=[_page(3, "text")], findings=[_finding()]
    )
    assert check_tenant_isolation(bundle) == []


def test_tenant_isolation_fails_when_a_finding_cites_a_page_outside_the_bundle():
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        pages=[_page(1, "text")],
        findings=[_finding(source_page=99)],
    )
    violations = check_tenant_isolation(bundle)
    assert len(violations) == 1
    assert "page 99" in violations[0].message


def test_tenant_isolation_skipped_when_bundle_has_no_pages():
    """A findings-only bundle (e.g. BOQ-only) has nothing to check against."""
    bundle = PipelineBundle(opportunity_id="o", workspace_id="w", findings=[_finding()])
    assert check_tenant_isolation(bundle) == []


# --------------------------------------------------------- 8. graceful degradation


def test_graceful_degradation_passes_with_no_unreadable_pages():
    bundle = PipelineBundle(opportunity_id="o", workspace_id="w")
    assert check_graceful_degradation(bundle) == []


def test_graceful_degradation_fails_when_unreadable_pages_are_silent():
    bundle = PipelineBundle(
        opportunity_id="o", workspace_id="w", unreadable_pages={("doc-1", 40)}
    )
    violations = check_graceful_degradation(bundle)
    assert any("no degradation note" in v.message for v in violations)


def test_graceful_degradation_passes_when_unreadable_pages_are_reported():
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        unreadable_pages={("doc-1", 40)},
        degradation_notes=["pages 40-55 unreadable, upload Excel BOQ"],
    )
    assert check_graceful_degradation(bundle) == []


def test_graceful_degradation_fails_on_a_quote_from_an_unreadable_page():
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        unreadable_pages={("doc-1", 3)},
        degradation_notes=["page 3 unreadable"],
        findings=[_finding(source_page=3)],
    )
    violations = check_graceful_degradation(bundle)
    assert any("recorded as unreadable" in v.message for v in violations)


# --------------------------------------------------------------------- 9. budget


def test_budget_passes_within_ceiling():
    bundle = PipelineBundle(
        opportunity_id="o", workspace_id="w", token_count=1000, token_ceiling=400_000
    )
    assert check_budget(bundle) == []


def test_budget_fails_over_the_token_ceiling():
    bundle = PipelineBundle(
        opportunity_id="o", workspace_id="w", token_count=500_000, token_ceiling=400_000
    )
    violations = check_budget(bundle)
    assert len(violations) == 1
    assert violations[0].invariant == "budget"


def test_budget_fails_over_the_wall_ceiling():
    bundle = PipelineBundle(
        opportunity_id="o", workspace_id="w", wall_seconds=2000, wall_ceiling=1500
    )
    assert len(check_budget(bundle)) == 1


def test_budget_zero_ceiling_disables_the_check():
    bundle = PipelineBundle(
        opportunity_id="o", workspace_id="w", token_count=10_000_000, token_ceiling=0
    )
    assert check_budget(bundle) == []


# -------------------------------------------------------------------- 10. no crash


def test_no_crash_passes_when_pipeline_completed():
    bundle = PipelineBundle(opportunity_id="o", workspace_id="w", pipeline_error=None)
    assert check_no_crash(bundle) == []


def test_no_crash_passes_for_a_classified_error():
    bundle = PipelineBundle(
        opportunity_id="o", workspace_id="w", pipeline_error="ocr_failed: pages 40-55 unreadable"
    )
    assert check_no_crash(bundle) == []


def test_no_crash_fails_for_a_raw_traceback():
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        pipeline_error='Traceback (most recent call last):\n  File "x.py", line 1\nValueError',
    )
    violations = check_no_crash(bundle)
    assert len(violations) == 1
    assert violations[0].invariant == "no_crash"


def test_no_crash_fails_for_an_empty_error_string():
    bundle = PipelineBundle(opportunity_id="o", workspace_id="w", pipeline_error="   ")
    assert len(check_no_crash(bundle)) == 1


# --------------------------------------------------------------- runner aggregation


def test_run_m1_ok_true_when_every_check_passes():
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        pages=[_page(3, "payment shall be released within 120 days")],
        findings=[_finding()],
    )
    result = run_m1(bundle)
    assert result.ok is True
    assert result.checks_run == 10
    assert result.violations == []


def test_run_m1_ok_false_and_reports_every_violation():
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        pages=[],  # quote will not be found anywhere
        findings=[_finding(amount_exposure=15000.5)],  # also a currency violation
    )
    result = run_m1(bundle)
    assert result.ok is False
    kinds = {v.invariant for v in result.violations}
    assert "quote_integrity" in kinds
    assert "currency_integrity" in kinds


def test_run_m1_summary_is_json_shaped():
    bundle = PipelineBundle(opportunity_id="opp-1", workspace_id="w")
    result = run_m1(bundle)
    summary = result.summary()
    assert summary["opportunity_id"] == "opp-1"
    assert summary["ok"] is True
    assert summary["checks_run"] == 10
    assert summary["violations"] == []


def test_by_invariant_groups_violations():
    bundle = PipelineBundle(
        opportunity_id="o",
        workspace_id="w",
        findings=[_finding(source_page=None, source_quote=None, explanation={"absence": False})],
    )
    result = run_m1(bundle)
    grouped = result.by_invariant()
    assert "citation_completeness" in grouped


# ----------------------------------------------------- integration: real pipeline

SAMPLE = None
try:
    from pathlib import Path

    SAMPLE = Path(__file__).resolve().parents[2] / "evals" / "in-works" / "sample_tender"
except Exception:  # pragma: no cover
    pass


def test_m1_against_the_real_boq_engine_output():
    """Runs the actual deterministic BOQ engine (not a synthetic fixture) and
    asserts the M1 arithmetic-closure and citation checks agree with it."""
    pack = RulePackLoader().get_pack("in-works")
    df = pd.read_csv(SAMPLE / "boq.csv")
    normalized = normalize(df, pack.unit_canon)
    findings = run_checks(
        normalized,
        tolerance=pack.boq_checks.arithmetic_tolerance,
        outlier_quantile=pack.boq_checks.qty_outlier_quantile,
        outlier_multiplier=pack.boq_checks.qty_outlier_multiplier,
    )
    finding_dicts = [f.model_dump() for f in findings]
    boq_rows = normalized.to_dict("records")

    bundle = PipelineBundle(
        opportunity_id="sample",
        workspace_id="w",
        findings=finding_dicts,
        boq_rows=boq_rows,
        boq_tolerance=pack.boq_checks.arithmetic_tolerance,
    )
    result = run_m1(bundle)
    # BOQ_DEFECT findings need no page (citation_completeness) and every
    # mismatching row is flagged (boq_arithmetic_closure) — both hold for real
    # engine output, not just for a hand-built fixture.
    assert result.ok, result.summary()


def test_m1_against_the_real_risk_engine_output():
    """Runs the actual risk engine with a classifier that returns a genuinely
    verbatim quote, proving quote_integrity and citation_completeness hold for
    real engine output shapes, not just synthetic ones."""
    pack = RulePackLoader().get_pack("in-works")
    ld_pattern = pack.patterns["liquidated_damages_uncapped"]

    clause_text = (
        "Liquidated damages for delay shall be levied at the rate of 1% per week "
        "of the contract value, with no maximum cap."
    )
    clauses = [{"id": "c1", "clause_ref": "GCC 14", "text": clause_text, "page_from": 5}]

    class _StubClassifier:
        def classify(self, pattern, candidates):
            return [
                {
                    "found": True,
                    "finding": "LD is uncapped at 1% per week.",
                    "facts": {"cap_absent": True, "rate_percent_per_week": 1.0},
                    "source_quote": clause_text,
                    "source_page": 5,
                }
            ]

    findings = run_pattern(ld_pattern, clauses, _StubClassifier())
    finding_dicts = [f.model_dump() for f in findings]

    bundle = PipelineBundle(
        opportunity_id="sample",
        workspace_id="w",
        pages=[_page(5, clause_text)],
        findings=finding_dicts,
    )
    result = run_m1(bundle)
    assert result.ok, result.summary()


# ------------------------------------------------------------------ DB adapter


@pytest.fixture
def session():
    engine = make_engine(Settings(database_url="sqlite+pysqlite:///:memory:"))
    Base.metadata.create_all(engine)
    return make_session_factory(engine)()


def test_db_adapter_builds_a_bundle_from_persisted_findings(session):
    from app.core.contracts.findings import Finding, FindingKind, FindingSource, Severity

    ws, opp = uuid.uuid4(), uuid.uuid4()
    FindingStore(session).replace_for_producer(
        ws,
        opp,
        "risk",
        [
            Finding(
                kind=FindingKind.RISK_CLAUSE,
                category="ld",
                severity=Severity.HIGH,
                title="t",
                detail="d",
                source=FindingSource.AI_SUGGESTION,
                source_page=1,
                source_quote="uncapped liquidated damages",
            )
        ],
    )

    bundle = bundle_from_opportunity(session, ws, opp)
    assert bundle.opportunity_id == str(opp)
    assert len(bundle.findings) == 1
    assert bundle.findings[0]["source_quote"] == "uncapped liquidated damages"


def test_db_adapter_is_workspace_scoped(session):
    """The check this test proves is the one `check_tenant_isolation` cannot: a
    bundle for workspace A must never contain workspace B's findings, because
    the query itself is workspace-scoped — not because a bundle-internal check
    happened to catch it after the fact."""
    from app.core.contracts.findings import Finding, FindingKind, FindingSource, Severity

    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    opp_a, opp_b = uuid.uuid4(), uuid.uuid4()
    store = FindingStore(session)
    f = Finding(
        kind=FindingKind.RISK_CLAUSE,
        category="ld",
        severity=Severity.HIGH,
        title="t",
        detail="d",
        source=FindingSource.AI_SUGGESTION,
    )
    store.replace_for_producer(ws_a, opp_a, "risk", [f])
    store.replace_for_producer(ws_b, opp_b, "risk", [f])

    bundle = bundle_from_opportunity(session, ws_a, opp_a)
    assert len(bundle.findings) == 1
    assert bundle.workspace_id == str(ws_a)


def test_db_adapter_carries_run_metadata_through(session):
    bundle = bundle_from_opportunity(
        session,
        uuid.uuid4(),
        uuid.uuid4(),
        token_count=5000,
        token_ceiling=10_000,
        wall_seconds=1.5,
        pipeline_error="ocr_failed",
    )
    assert bundle.token_count == 5000
    assert bundle.pipeline_error == "ocr_failed"
    result = run_m1(bundle)
    assert result.ok  # a classified error and in-budget tokens are both fine
