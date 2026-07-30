"""Risk engine: deterministic severity + retrieval + quote-verification tests
(no LLM), plus full-stack run with a fake classifier and absence detection."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.risk.engine import retrieve_candidates, run_pattern, verify_quote
from app.modules.risk.severity import evaluate_severity
from app.modules.rulepacks.loader import RulePackLoader
from tests.helpers import auth_headers

# ---- deterministic severity (the invariant: severity is code, not LLM) ----


def test_severity_rules_from_pack():
    r_ld = "critical if cap_absent else high if rate_percent_per_week > 0.5 else medium"
    assert evaluate_severity(r_ld, {"cap_absent": True}) == "critical"
    assert evaluate_severity(r_ld, {"cap_absent": False, "rate_percent_per_week": 1.0}) == "high"
    assert evaluate_severity(r_ld, {"cap_absent": False, "rate_percent_per_week": 0.4}) == "medium"

    r_esc = "critical if project_duration_months > 18 else high"
    assert evaluate_severity(r_esc, {"project_duration_months": 30}) == "critical"
    assert evaluate_severity(r_esc, {"project_duration_months": 6}) == "high"


def test_severity_missing_facts_default_and_bad_rule_fallback():
    # missing fact is an error → falls back to default instead of silently 0
    assert evaluate_severity("critical if cap_absent else low", {}) == "medium"
    # malformed rule → default
    assert evaluate_severity("this is not valid python !!", {}) == "medium"
    # non-severity result → default
    assert evaluate_severity("1 + 1 if x else 3", {"x": True}, default="info") == "info"


# ---- retrieval + quote verification ---------------------------------------

CLAUSES = [
    {
        "id": "1",
        "clause_ref": "14",
        "text": "The contract is on a firm price basis and no escalation shall be payable.",
        "page_from": 2,
    },
    {
        "id": "2",
        "clause_ref": "33",
        "text": "Liquidated damages at 1% of the contract value per week of delay.",
        "page_from": 4,
    },
]


def test_retrieve_by_anchor():
    got = retrieve_candidates(CLAUSES, ["no escalation shall be payable"])
    assert [c["id"] for c in got] == ["1"]
    assert retrieve_candidates(CLAUSES, ["nonexistent anchor"]) == []


def test_verify_quote():
    assert verify_quote("firm price basis and no escalation shall be payable", CLAUSES)
    assert not verify_quote("a completely invented quotation not present", CLAUSES)
    assert not verify_quote("", CLAUSES)


# ---- run_pattern with a fake classifier -----------------------------------


class _FakeClassifier:
    """Deterministic stand-in for the LLM (facts + a real verbatim quote)."""

    def __init__(self, result):
        self.result = result

    def classify(self, pattern, candidates):
        return self.result


def _pattern(pack, pid):
    return pack.patterns[pid]


def test_run_pattern_deterministic_severity_and_verified_quote():
    pack = RulePackLoader().get_pack("in-works")
    pattern = _pattern(pack, "liquidated_damages_uncapped")
    clf = _FakeClassifier(
        [
            {
                "found": True,
                "finding": "LD 1%/week with no cap.",
                "facts": {"cap_absent": True, "rate_percent_per_week": 1.0},
                "source_quote": "Liquidated damages at 1% of the contract value per week of delay.",
                "source_page": 4,
            }
        ]
    )
    findings = run_pattern(pattern, CLAUSES, clf)
    assert len(findings) == 1
    f = findings[0]
    assert f.severity.value == "critical"  # from the rule, not the classifier
    assert f.source_quote is not None  # quote verified against the clause
    assert f.pattern_id == "liquidated_damages_uncapped"
    assert f.source.value == "ai_suggestion"
    assert f.explanation is not None
    assert f.explanation["matched_pattern"]["id"] == "liquidated_damages_uncapped"
    assert "industry_reason" in f.explanation
    assert f.explanation["absence"] is False


def test_run_pattern_drops_unverified_quote():
    pack = RulePackLoader().get_pack("in-works")
    pattern = _pattern(pack, "liquidated_damages_uncapped")
    clf = _FakeClassifier(
        [
            {
                "found": True,
                "finding": "x",
                "facts": {"cap_absent": True},
                "source_quote": "a quote that is nowhere in the source text",
                "source_page": 4,
            }
        ]
    )
    f = run_pattern(pattern, CLAUSES, clf)[0]
    assert f.source_quote is None
    assert "unverified quote" in f.detail


def test_absence_detection_when_no_candidates():
    pack = RulePackLoader().get_pack("in-works")
    pattern = _pattern(pack, "price_escalation_barred")  # absence_is_finding: true
    findings = run_pattern(pattern, [], _FakeClassifier([]), {"project_duration_months": 30})
    assert len(findings) == 1
    assert "ABSENT" in findings[0].title
    assert findings[0].severity.value == "critical"  # duration>18
    assert findings[0].explanation["absence"] is True


# ---- integration ----------------------------------------------------------


@pytest.fixture
def client():
    application = create_app(
        Settings(
            enabled_modules="health,rulepacks,auth,ingestion,risk",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "e@x.com")

def test_run_endpoint_absence_finding_without_llm(client):
    # No API key in tests → NullClassifier. Absence detection still works: an
    # opportunity with NO escalation clause yields the escalation absence finding.
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Bridge"}, headers=headers
    ).json()["id"]
    gcc_text = "[p1]\nClause 5 — Scope of work. Build a bridge."
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "gcc.pdf", "sample_text": gcc_text},
        headers=headers,
    )
    out = client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers).json()
    cats = {f["category"] for f in out["findings"]}
    assert "escalation" in cats  # absence finding fired deterministically
