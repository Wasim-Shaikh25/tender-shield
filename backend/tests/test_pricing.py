"""Tests for the `pricing` module (TS-201–207).

Highest-liability module in the product (spec §Guardrails), so the test
emphasis matches: worked examples per formula, missing-input honesty (never a
default), determinism, the two-band rate-match confidence split, the
mandatory cashflow assumptions block, the no-LLM-import guarantee, and the
review-export gate end to end through the real router.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.pricing.benchmark import benchmark
from app.modules.pricing.cashflow import CashflowInputs, run_cashflow
from app.modules.pricing.formulas import (
    MissingInputs,
    escalation_unhedged,
    ld_exposure_cap,
    payment_delay_financing_cost,
)
from app.modules.pricing.loading import compute_loadings
from app.modules.rulepacks.loader import RulePackLoader
from tests.helpers import auth_headers

PRICING_MODULES_DIR = Path(__file__).resolve().parents[1] / "app" / "modules" / "pricing"

CONTRACT_VALUE = 100_000_00  # ₹1,00,000 in paise


# ------------------------------------------------------------------- formulas


def test_escalation_unhedged_worked_example():
    # 24-month contract, 6%/yr index -> 12% of contract value
    facts = {"project_duration_months": 24, "index_series": 0.06}
    amount = escalation_unhedged(facts, contract_value_minor=CONTRACT_VALUE)
    assert amount == round(CONTRACT_VALUE * 0.12)


def test_escalation_unhedged_missing_input_raises():
    with pytest.raises(MissingInputs) as exc:
        escalation_unhedged({"project_duration_months": 24}, contract_value_minor=CONTRACT_VALUE)
    assert "index_series" in exc.value.missing


def test_ld_exposure_cap_worked_example_uncapped_by_the_rate():
    # 0.5%/week x 10 weeks = 5%, under the 10% cap -> raw exposure applies
    facts = {"rate_percent_per_week": 0.5, "cap_percent": 10, "weeks_at_risk": 10}
    amount = ld_exposure_cap(facts, contract_value_minor=CONTRACT_VALUE)
    assert amount == round(CONTRACT_VALUE * 0.05)


def test_ld_exposure_cap_worked_example_bounded_by_the_cap():
    # 1%/week x 20 weeks = 20%, capped at 10%
    facts = {"rate_percent_per_week": 1.0, "cap_percent": 10, "weeks_at_risk": 20}
    amount = ld_exposure_cap(facts, contract_value_minor=CONTRACT_VALUE)
    assert amount == round(CONTRACT_VALUE * 0.10)


def test_ld_exposure_cap_missing_cap_percent_is_not_guessed():
    """An uncapped LD clause (no cap fact) must never fall back to an assumed
    ceiling — that would be exactly the invented number the product exists to
    prevent (formulas.py docstring)."""
    with pytest.raises(MissingInputs) as exc:
        ld_exposure_cap(
            {"rate_percent_per_week": 1.0, "weeks_at_risk": 20},
            contract_value_minor=CONTRACT_VALUE,
        )
    assert exc.value.missing == ["cap_percent"]


def test_payment_delay_financing_cost_worked_example():
    # 90-day terms, 30-day baseline -> 60 extra days at 12%/yr
    facts = {"payment_days": 90, "cost_of_capital_pa": 0.12}
    amount = payment_delay_financing_cost(facts, contract_value_minor=CONTRACT_VALUE)
    expected = round(CONTRACT_VALUE * (0.12 / 365.0) * 60)
    assert amount == expected


def test_payment_delay_within_baseline_produces_zero():
    facts = {"payment_days": 20, "cost_of_capital_pa": 0.12}
    assert payment_delay_financing_cost(facts, contract_value_minor=CONTRACT_VALUE) == 0


# -------------------------------------------------------------- loading engine


class _Pattern:
    def __init__(self, price_impact):
        self.price_impact = price_impact


class _Impact:
    def __init__(self, basis, formula, inputs):
        self.basis = basis
        self.formula = formula
        self.inputs = inputs


def _escalation_pattern():
    return _Pattern(
        _Impact(
            "percent_of_contract_value",
            "escalation_unhedged",
            ["project_duration_months", "index_series"],
        )
    )


def test_loading_computes_from_accepted_findings_only():
    findings = [
        {"id": "f1", "pattern_id": "p1", "review_status": "accepted"},
        {"id": "f2", "pattern_id": "p1", "review_status": "proposed"},
    ]
    patterns = {"p1": _escalation_pattern()}
    facts = {
        "f1": {"project_duration_months": 24, "index_series": 0.06},
        "f2": {"project_duration_months": 24, "index_series": 0.06},
    }
    results = compute_loadings(
        findings, patterns, facts,
        contract_value_minor=CONTRACT_VALUE, currency="INR", rulepack_version="v1",
    )
    assert len(results) == 1
    assert results[0].finding_id == "f1"
    assert results[0].produced is True


def test_loading_missing_input_produces_no_loading_never_a_default():
    findings = [{"id": "f1", "pattern_id": "p1", "review_status": "accepted"}]
    patterns = {"p1": _escalation_pattern()}
    results = compute_loadings(
        findings, patterns, {"f1": {"project_duration_months": 24}},  # index_series missing
        contract_value_minor=CONTRACT_VALUE, currency="INR", rulepack_version="v1",
    )
    assert results[0].produced is False
    assert results[0].amount_minor is None
    assert "index_series" in results[0].missing_inputs
    assert results[0].reason == "missing required facts"


def test_loading_pattern_without_price_impact_is_reported_not_silently_dropped():
    findings = [{"id": "f1", "pattern_id": "p1", "review_status": "accepted"}]
    patterns = {"p1": _Pattern(None)}
    results = compute_loadings(
        findings, patterns, {},
        contract_value_minor=CONTRACT_VALUE, currency="INR", rulepack_version="v1",
    )
    assert len(results) == 1
    assert results[0].produced is False
    assert "no price_impact" in results[0].reason


def test_loading_is_byte_identical_on_rerun():
    findings = [{"id": "f1", "pattern_id": "p1", "review_status": "accepted"}]
    patterns = {"p1": _escalation_pattern()}
    facts = {"f1": {"project_duration_months": 18, "index_series": 0.05}}
    kwargs = dict(
        contract_value_minor=CONTRACT_VALUE, currency="INR", rulepack_version="v1"
    )
    a = compute_loadings(findings, patterns, facts, **kwargs)
    b = compute_loadings(findings, patterns, facts, **kwargs)
    assert [r.to_dict() for r in a] == [r.to_dict() for r in b]


def test_loading_unregistered_formula_is_reported():
    findings = [{"id": "f1", "pattern_id": "p1", "review_status": "accepted"}]
    patterns = {"p1": _Pattern(_Impact("percent_of_contract_value", "not_a_real_formula", ["x"]))}
    results = compute_loadings(
        findings, patterns, {}, contract_value_minor=CONTRACT_VALUE,
        currency="INR", rulepack_version="v1",
    )
    assert results[0].produced is False
    assert "not registered" in results[0].reason


# ------------------------------------------------------------- rate benchmark


class _ScheduleItem:
    def __init__(self, code, description, unit, rate_minor):
        self.code = code
        self.description = description
        self.unit = unit
        self.rate_minor = rate_minor


class _Schedule:
    def __init__(self, items, id="cpwd/2026", confidence="unvalidated"):
        self.items = items
        self.id = id
        self.confidence = confidence


def test_benchmark_code_match_is_high_confidence():
    schedule = _Schedule([_ScheduleItem("5.9", "Cement concrete work", "cum", 850000)])
    rows = [
        {"src_row": 1, "item_code": "5.9", "description": "Cement concrete work",
         "unit_canon": "m3", "rate": 9000.0}
    ]
    result = benchmark(rows, schedule)
    assert len(result.code_matched) == 1
    assert result.code_matched[0].matched_by == "code"
    assert result.headline_variance_pct is not None


def test_benchmark_description_match_is_excluded_from_headline():
    schedule = _Schedule(
        [_ScheduleItem("5.9", "Providing and laying cement concrete", "cum", 850000)]
    )
    rows = [
        {"src_row": 1, "item_code": "", "description": "Providing and laying cement concrete",
         "unit_canon": "m3", "rate": 9000.0}
    ]
    result = benchmark(rows, schedule)
    assert len(result.description_matched) == 1
    assert len(result.code_matched) == 0
    # Nothing code-matched -> headline is None, not a coverage-diluted number.
    assert result.headline_variance_pct is None


def test_benchmark_unmatched_is_reported_never_force_matched():
    schedule = _Schedule([_ScheduleItem("5.9", "Cement concrete work", "cum", 850000)])
    rows = [{"src_row": 1, "item_code": "", "description": "Completely unrelated item",
             "unit_canon": "nos", "rate": 500.0}]
    result = benchmark(rows, schedule)
    assert len(result.unmatched) == 1
    assert result.unmatched[0].matched_by == "unmatched"


def test_benchmark_with_no_schedule_reports_everything_unmatched():
    rows = [
        {"src_row": 1, "item_code": "5.9", "description": "x", "unit_canon": "cum", "rate": 100.0}
    ]
    result = benchmark(rows, None)
    assert len(result.unmatched) == 1
    assert result.schedule_id is None


def test_benchmark_headline_variance_is_value_weighted():
    schedule = _Schedule([
        _ScheduleItem("1", "A", "cum", 100_00),
        _ScheduleItem("2", "B", "cum", 1000_00),
    ])
    rows = [
        {"src_row": 1, "item_code": "1", "description": "A", "unit_canon": "cum", "rate": 110.0},
        {"src_row": 2, "item_code": "2", "description": "B", "unit_canon": "cum", "rate": 1000.0},
    ]
    result = benchmark(rows, schedule)
    # (11000 - 10000 + 100000 - 100000) / (10000 + 100000) * 100
    assert round(result.headline_variance_pct, 4) == round((1000 / 110000) * 100, 4)


# ------------------------------------------------------------------- cashflow


def test_cashflow_missing_facts_are_disclosed_in_assumptions():
    inputs = CashflowInputs(
        contract_value_minor=CONTRACT_VALUE, duration_months=12, cost_of_capital_pa=0.10
    )
    result = run_cashflow(inputs, currency="INR")
    assert any("even monthly billing" in a for a in result.assumptions)
    assert any("payment_days not supplied" in a for a in result.assumptions)
    assert any("retention_pct not supplied" in a for a in result.assumptions)


def test_cashflow_reports_peak_requirement_and_month():
    inputs = CashflowInputs(
        contract_value_minor=CONTRACT_VALUE,
        duration_months=6,
        cost_of_capital_pa=0.10,
        payment_days=90,
        retention_pct=0.10,
    )
    result = run_cashflow(inputs, currency="INR")
    assert result.peak_requirement_minor >= 0
    assert 1 <= result.peak_month <= 6
    assert len(result.monthly) == 6


def test_cashflow_billing_totals_the_contract_value_when_even():
    inputs = CashflowInputs(
        contract_value_minor=100_007, duration_months=3, cost_of_capital_pa=0.10
    )
    result = run_cashflow(inputs, currency="INR")
    assert sum(m.billed_minor for m in result.monthly) == 100_007


def test_cashflow_no_shortfall_means_zero_financing_cost():
    inputs = CashflowInputs(
        contract_value_minor=CONTRACT_VALUE,
        duration_months=6,
        cost_of_capital_pa=0.10,
        payment_days=0,
        retention_pct=0,
    )
    result = run_cashflow(inputs, currency="INR")
    assert result.total_financing_cost_minor == 0


def test_cashflow_supplied_facts_do_not_generate_their_own_assumption():
    inputs = CashflowInputs(
        contract_value_minor=CONTRACT_VALUE,
        duration_months=6,
        cost_of_capital_pa=0.10,
        payment_days=45,
        retention_pct=0.05,
        retention_release_month=6,
    )
    result = run_cashflow(inputs, currency="INR")
    assert not any("payment_days not supplied" in a for a in result.assumptions)
    assert not any("retention_pct not supplied" in a for a in result.assumptions)


# ------------------------------------------------------ rulepack integration


def test_price_impact_loads_from_the_real_rulepack():
    pack = RulePackLoader().get_pack("in-works")
    assert pack.patterns["price_escalation_barred"].price_impact.formula == "escalation_unhedged"
    assert pack.patterns["liquidated_damages_uncapped"].price_impact.formula == "ld_exposure_cap"


def test_rate_schedules_empty_by_design_and_does_not_error():
    """rulepacks/in-works/rates/ ships empty (see its README) — the loader must
    treat that as zero schedules, not a load error."""
    pack = RulePackLoader().get_pack("in-works", reload=True)
    assert pack.rate_schedules == {}
    assert not any(k.startswith("rates/") for k in pack.load_errors)


# --------------------------------------------------------- no-LLM-dependency


def test_module_has_no_llm_client_dependency():
    """Guardrail 5 (spec): numbers never come from the LLM, enforced by test.
    Statically checks every source file's imports rather than relying on
    behavior, so a future accidental `import openai` fails CI immediately."""
    banned = {"openai", "app.core.llm"}
    offending = []
    for path in PRICING_MODULES_DIR.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if any(name == b or name.startswith(b + ".") for b in banned):
                    offending.append(f"{path.name}: {name}")
    assert not offending, f"pricing module imports an LLM client: {offending}"


# --------------------------------------------------------------- integration


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules=(
                "health,rulepacks,auth,ingestion,findings,risk,review,boq,pricing"
            ),
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    return auth_headers(client, "pricing@x.com")


def _opp_with_findings(client, headers):
    """Mirrors test_export.py's helper: with NullClassifier (no API key),
    only absence-type patterns fire. price_escalation_barred is one of them
    and already carries a price_impact block, so this is real end-to-end
    coverage, not a synthetic fixture."""
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Bridge"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "gcc.pdf", "sample_text": "[p1]\nClause 5 — Scope. Build a bridge."},
        headers=headers,
    )
    client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers)
    return opp_id


def test_loading_endpoint_blocked_until_review_complete(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    r = client.get(
        f"/api/pricing/opportunities/{opp_id}/loading",
        params={"contract_value_minor": CONTRACT_VALUE},
        headers=headers,
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "review_incomplete"


def test_loading_endpoint_after_review_reports_missing_facts(client):
    """No facts were supplied, so the real end-to-end loading correctly
    produces no amount — proving the API-level honesty guarantee, not just
    the unit-level one."""
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    for f in client.get(
        f"/api/review/opportunities/{opp_id}/queue", headers=headers
    ).json()["findings"]:
        client.post(
            f"/api/review/findings/{f['id']}",
            json={"opportunity_id": opp_id, "decision": "accepted"},
            headers=headers,
        )

    r = client.get(
        f"/api/pricing/opportunities/{opp_id}/loading",
        params={"contract_value_minor": CONTRACT_VALUE},
        headers=headers,
    )
    assert r.status_code == 200
    loadings = r.json()["loadings"]
    assert len(loadings) == 1
    assert loadings[0]["produced"] is False
    assert loadings[0]["reason"] == "missing required facts"


def test_loading_endpoint_with_facts_produces_an_amount(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    for f in client.get(
        f"/api/review/opportunities/{opp_id}/queue", headers=headers
    ).json()["findings"]:
        client.post(
            f"/api/review/findings/{f['id']}",
            json={"opportunity_id": opp_id, "decision": "accepted"},
            headers=headers,
        )
        finding_id = f["id"]

    import json as _json

    r = client.get(
        f"/api/pricing/opportunities/{opp_id}/loading",
        params={
            "contract_value_minor": CONTRACT_VALUE,
            "facts": _json.dumps(
                {finding_id: {"project_duration_months": 24, "index_series": 0.06}}
            ),
        },
        headers=headers,
    )
    assert r.status_code == 200
    loadings = r.json()["loadings"]
    assert loadings[0]["produced"] is True
    assert loadings[0]["amount_minor"] == round(CONTRACT_VALUE * 0.12)


def test_cashflow_endpoint_blocked_until_review_complete(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    r = client.post(
        f"/api/pricing/opportunities/{opp_id}/cashflow",
        json={
            "contract_value_minor": CONTRACT_VALUE,
            "duration_months": 12,
            "cost_of_capital_pa": 0.1,
        },
        headers=headers,
    )
    assert r.status_code == 409


def test_cashflow_endpoint_after_review(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    for f in client.get(
        f"/api/review/opportunities/{opp_id}/queue", headers=headers
    ).json()["findings"]:
        client.post(
            f"/api/review/findings/{f['id']}",
            json={"opportunity_id": opp_id, "decision": "accepted"},
            headers=headers,
        )

    r = client.post(
        f"/api/pricing/opportunities/{opp_id}/cashflow",
        json={
            "contract_value_minor": CONTRACT_VALUE,
            "duration_months": 12,
            "cost_of_capital_pa": 0.1,
        },
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["assumptions"]
    assert len(body["monthly"]) == 12


def test_rate_benchmark_endpoint_with_no_schedule_reports_unmatched(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    for f in client.get(
        f"/api/review/opportunities/{opp_id}/queue", headers=headers
    ).json()["findings"]:
        client.post(
            f"/api/review/findings/{f['id']}",
            json={"opportunity_id": opp_id, "decision": "accepted"},
            headers=headers,
        )

    csv = "src_row,item_code,description,unit_raw,qty,rate,amount\n1,X,concrete,cum,10,100,1000\n"
    r = client.post(
        f"/api/pricing/opportunities/{opp_id}/rate-benchmark",
        json={"csv": csv},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["unmatched"]) == 1
    assert body["headline_variance_pct"] is None
