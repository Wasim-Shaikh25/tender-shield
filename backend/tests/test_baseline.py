"""Baseline lock (TS-041): deterministic notice extraction (unit) + the
freeze/verify/compare/handover flow through the app (auth-gated, review-gated),
and a boot check with the module disabled."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.baseline.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.review.models  # noqa: F401
import app.modules.standards.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.baseline.notices import extract_notice_rules
from tests.helpers import auth_headers, auth_headers_and_workspace

MODULES = "health,rulepacks,auth,ingestion,findings,risk,review,standards,baseline"


# ---- deterministic notice extraction (spec B4 / A3) -----------------------


def test_notice_extraction_normalises_and_keeps_provenance():
    findings = [
        {
            "category": "termination",
            "title": "Notice window",
            "detail": "Either party may terminate within 14 days of a breach.",
            "source_quote": "terminate within 14 days of a breach",
            "source_page": 7,
        },
        {
            "category": "claims",
            "title": "Claim bar",
            "detail": "A claim requires 28 days' notice failing which it is time-barred.",
            "source_quote": "28 days' notice",
            "source_page": 9,
        },
    ]
    rules = extract_notice_rules(findings)
    by_days = {r.days: r for r in rules}
    assert 14 in by_days and by_days[14].source_page == 7
    assert 28 in by_days and by_days[28].category == "claims"


def test_notice_extraction_week_month_normalisation_and_dedup():
    findings = [
        {"category": "payment", "title": "t", "detail": "pay within 2 weeks", "source_page": 1},
        {"category": "payment", "title": "t2", "detail": "pay within 2 weeks", "source_page": 2},
        {"category": "defects", "title": "t3", "detail": "notify within 1 month", "source_page": 3},
    ]
    rules = extract_notice_rules(findings)
    days = sorted(r.days for r in rules)
    assert days == [14, 30]  # 2 weeks, 1 month; the duplicate 14/payment deduped


# ---- full-stack freeze flow -----------------------------------------------


@pytest.fixture
def client():
    application = create_app(Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:"))
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "b@x.com")


def _opp_with_findings(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Metro Depot"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "gcc.pdf", "sample_text": "[p1]\nClause 5 — Scope. Build a depot."},
        headers=headers,
    )
    client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers)
    return opp_id


def _accept_all(client, headers, opp_id, decision="accepted"):
    queue = client.get(f"/api/review/opportunities/{opp_id}/queue", headers=headers).json()[
        "findings"
    ]
    for f in queue:
        client.post(
            f"/api/review/findings/{f['id']}",
            json={"opportunity_id": opp_id, "decision": decision},
            headers=headers,
        )
    return queue


def test_freeze_blocked_until_review_then_seals_and_verifies(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)

    # A1: freeze before review completes is refused.
    blocked = client.post(
        f"/api/baseline/opportunities/{opp_id}/freeze", json={"source": "tender"}, headers=headers
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "review_incomplete"

    _accept_all(client, headers, opp_id)

    sealed = client.post(
        f"/api/baseline/opportunities/{opp_id}/freeze",
        json={"source": "tender", "note": "post-award freeze"},
        headers=headers,
    )
    assert sealed.status_code == 200
    body = sealed.json()
    assert body["version"] == 1
    assert len(body["content_sha256"]) == 64  # sha-256 hex

    # A2: the seal verifies intact.
    bid = body["id"]
    v = client.get(f"/api/baseline/baselines/{bid}/verify", headers=headers).json()
    assert v["intact"] is True
    assert v["sealed_hash"] == v["recomputed_hash"]


def test_award_vs_tender_compare_and_handover(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    _accept_all(client, headers, opp_id, decision="accepted")

    client.post(
        f"/api/baseline/opportunities/{opp_id}/freeze", json={"source": "tender"}, headers=headers
    )

    # Negotiation drops the finding; re-freeze as the award baseline.
    _accept_all(client, headers, opp_id, decision="rejected")
    award = client.post(
        f"/api/baseline/opportunities/{opp_id}/freeze", json={"source": "award"}, headers=headers
    ).json()
    assert award["version"] == 2

    # A4: compare shows the accepted finding removed at award.
    delta = client.get(f"/api/baseline/opportunities/{opp_id}/compare", headers=headers).json()
    assert delta["tender_version"] == 1 and delta["award_version"] == 2
    assert len(delta["removed"]) >= 1

    # A5: handover pack surfaces the sealed hash from the latest baseline.
    pack = client.get(f"/api/baseline/opportunities/{opp_id}/handover", headers=headers).json()
    assert len(pack["sealed_hash"]) == 64
    assert pack["opportunity"]["title"] == "Metro Depot"


def test_notice_register_falls_back_to_live_before_seal(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    reg = client.get(
        f"/api/baseline/opportunities/{opp_id}/notice-register", headers=headers
    ).json()
    assert reg["source"] == "live"  # nothing sealed yet
    assert "rules" in reg


def test_notice_register_reads_clauses_without_llm(client):
    # The register must populate from real contract text even with no LLM:
    # a clause carrying a "within 14 days" bar is picked up deterministically.
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Depot"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": (
                "[p3]\nClause 44 — Claims. The contractor shall notify any claim "
                "within 14 days of the event, failing which it shall be time-barred."
            ),
        },
        headers=headers,
    )
    reg = client.get(
        f"/api/baseline/opportunities/{opp_id}/notice-register", headers=headers
    ).json()
    assert any(r["days"] == 14 for r in reg["rules"])
    # The 14-day window mentions "claim" → classified against the standard.
    assert any(r["category"] == "claim" for r in reg["rules"])


def test_notice_register_flags_expected_regime_gaps(client):
    # Standards-aware: a contract with only a claims window should still flag the
    # OTHER expected regimes (EOT, payment, variation, …) as gaps — universal
    # base + India overlay drive this deterministically, no LLM.
    headers = _auth(client)
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Depot"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": (
                "[p3]\nClause 44 — Claims. Notify any claim within 14 days, "
                "failing which it is time-barred."
            ),
        },
        headers=headers,
    )
    reg = client.get(
        f"/api/baseline/opportunities/{opp_id}/notice-register", headers=headers
    ).json()
    assert reg["region"] == "IN"
    gap_keys = {g["key"] for g in reg["gaps"]}
    # claim is present, so it must NOT be a gap; EOT/payment are expected + absent.
    assert "claim" not in gap_keys
    assert "extension_of_time" in gap_keys
    assert "payment" in gap_keys


def _opp_with_claims_clause(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Depot"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": (
                "[p3]\nClause 44 — Claims. Notify any claim within 14 days, "
                "failing which it is time-barred."
            ),
        },
        headers=headers,
    )
    return opp_id


def test_org_custom_standard_prevails_and_adds_gap(client):
    # A firm's own standard adds a "handover" regime it always requires; in
    # prevail mode it's merged onto universal+IN and, being expected+absent,
    # shows up as a gap tagged origin=org.
    headers = _auth(client)
    opp_id = _opp_with_claims_clause(client, headers)
    client.put(
        "/api/standards/notice",
        json={
            "mode": "prevail",
            "categories": [
                {
                    "key": "handover",
                    "label": "Site handover / possession notice",
                    "typical_days": 7,
                    "expected": True,
                    "keywords": ["handover", "possession"],
                }
            ],
        },
        headers=headers,
    )
    reg = client.get(
        f"/api/baseline/opportunities/{opp_id}/notice-register", headers=headers
    ).json()
    handover_gaps = [g for g in reg["gaps"] if g["key"] == "handover"]
    assert handover_gaps and handover_gaps[0]["origin"] == "org"


def test_org_standard_side_by_side_keeps_both(client):
    # side_by_side: an org "claim" regime coexists with the rule-pack claim
    # rather than replacing it (the contract's claim window still classifies).
    headers = _auth(client)
    opp_id = _opp_with_claims_clause(client, headers)
    client.put(
        "/api/standards/notice",
        json={
            "mode": "side_by_side",
            "categories": [
                {
                    "key": "claim",
                    "label": "Our stricter claim policy",
                    "typical_days": 7,
                    "keywords": ["claim"],
                }
            ],
        },
        headers=headers,
    )
    reg = client.get(
        f"/api/baseline/opportunities/{opp_id}/notice-register", headers=headers
    ).json()
    # The contract's 14-day claim window is still detected and classified.
    assert any(r["days"] == 14 and r["category"] == "claim" for r in reg["rules"])


def test_app_boots_with_baseline_disabled():
    # A6: Phase-1 subset boots and works without the baseline module.
    application = create_app(
        Settings(
            enabled_modules="health,rulepacks,auth,ingestion,findings,risk,review",
            database_url="sqlite:///:memory:",
        )
    )
    loaded = {s.name for s in application.state.load_report.loaded}
    assert "baseline" not in loaded
    assert not application.state.ctx.registry.has("baseline.service_factory")


def test_compare_award_reports_clause_concession(client):
    headers = _auth(client)
    opp_id = _opp_with_findings(client, headers)
    _accept_all(client, headers, opp_id, decision="accepted")
    client.post(
        f"/api/baseline/opportunities/{opp_id}/freeze", json={"source": "tender"}, headers=headers
    )
    award_text = (
        "[p4]\nClause 21 — Payment. Interim payment shall be released within "
        "90 (ninety) days of certification."
    )
    client.post(
        f"/api/baseline/opportunities/{opp_id}/award-document",
        files={"file": ("award.csv", award_text.encode(), "text/csv")},
        headers=headers,
    )
    client.post(
        f"/api/baseline/opportunities/{opp_id}/freeze", json={"source": "award"}, headers=headers
    )
    delta = client.get(
        f"/api/baseline/opportunities/{opp_id}/compare/award", headers=headers
    )
    assert delta.status_code == 200, delta.text
    body = delta.json()
    assert body["baseline_refs"]["tender_id"]
    assert "clauses" in body
    assert body["clauses"]["added"] or body["clauses"]["changed"]


def test_watchlist_seeded_on_freeze_and_owner_assignable(client):
    headers, workspace_id = auth_headers_and_workspace(client, "watch@example.com")
    opp_id = _opp_with_findings(client, headers)
    reg = client.app.state.ctx.registry
    Session = reg.require("db.sessionmaker")
    with Session() as session:
        from app.modules.findings.store import FindingStore

        store = FindingStore(session)
        for row in store.list(workspace_id, opp_id):
            row.severity = "critical"
        session.commit()
    _accept_all(client, headers, opp_id, decision="accepted")
    client.post(
        f"/api/baseline/opportunities/{opp_id}/freeze", json={"source": "tender"}, headers=headers
    )
    controls = client.get(
        f"/api/baseline/opportunities/{opp_id}/watchlist", headers=headers
    ).json()["controls"]
    assert len(controls) >= 1
    user_id = client.get("/api/auth/me", headers=headers).json()["user_id"]
    updated = client.put(
        f"/api/baseline/watchlist/{controls[0]['id']}",
        headers=headers,
        json={
            "owner_user_id": user_id,
            "trigger_text": "Practical completion",
            "review_cadence": "weekly",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["owner_user_id"] == user_id
    assert updated.json()["review_cadence"] == "weekly"
