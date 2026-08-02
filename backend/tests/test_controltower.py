"""Control tower integration tests (TS-271–TS-280)."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.baseline.models  # noqa: F401
import app.modules.billing.models  # noqa: F401
import app.modules.change.models  # noqa: F401
import app.modules.claims.models  # noqa: F401
import app.modules.controltower  # noqa: F401
import app.modules.evidence.models  # noqa: F401
import app.modules.express.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.outcomes.models  # noqa: F401
import app.modules.review.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = (
    "health,rulepacks,auth,ingestion,findings,risk,review,baseline,change,evidence,claims,outcomes,controltower,billing,express"
)


@pytest.fixture
def client():
    application = create_app(
        Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:")
    )
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _auth(client):
    return auth_headers(client, "controltower@x.com")


def _setup_project(client, headers, contract_value_minor: int = 1_000_000):
    opp_id = client.post(
        "/api/ingestion/opportunities",
        json={
            "title": "Control tower site",
            "contract_value_minor": contract_value_minor,
            "currency": "INR",
        },
        headers=headers,
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={
            "filename": "gcc.pdf",
            "sample_text": (
                "[p1]\nClause 12 — Variations require 28 days notice.\n"
                "[p2]\nLast date of submission 15 March 2026.\n"
            ),
        },
        headers=headers,
    )
    client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers)
    for finding in client.get(
        f"/api/review/opportunities/{opp_id}/queue", headers=headers
    ).json()["findings"]:
        client.post(
            f"/api/review/findings/{finding['id']}",
            json={"opportunity_id": opp_id, "decision": "accepted"},
            headers=headers,
        )
    client.post(
        f"/api/baseline/opportunities/{opp_id}/freeze",
        json={"source": "tender"},
        headers=headers,
    ).raise_for_status()
    event = client.post(
        f"/api/change/opportunities/{opp_id}/events",
        json={
            "title": "Revised pile depth",
            "reason": "drawing_revision",
            "sources": [
                {"source_quote": "extra pile depth required", "source_page": 4}
            ],
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/change/events/{event['id']}/confirmations",
        json={"outcome": "changed"},
        headers=headers,
    ).raise_for_status()
    return opp_id, event["id"], event["baseline_id"]


def test_exposure_model_computes_submitted_certified_rejected(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)

    # Draft claim linked to the change event counts as unnotified change.
    client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Unnotified pile depth",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
            "claim_amount_minor": 100000,
        },
        headers=headers,
    ).raise_for_status()

    # Submitted claim ages until settled.
    submitted = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Submitted claim",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
            "claim_amount_minor": 250000,
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/claims/claims/{submitted['id']}/submit",
        headers=headers,
    ).raise_for_status()

    # Settled claim becomes certified value.
    settled = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Settled claim",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
            "claim_amount_minor": 150000,
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/claims/claims/{settled['id']}/settlement",
        json={"outcome": "approved", "settled_amount_minor": 125000},
        headers=headers,
    ).raise_for_status()

    # Withdrawn claim counts in rejected/withdrawn value.
    withdrawn = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Withdrawn claim",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
            "claim_amount_minor": 50000,
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/claims/claims/{withdrawn['id']}/settlement",
        json={"outcome": "withdrawn", "settled_amount_minor": 0},
        headers=headers,
    ).raise_for_status()

    exposure = client.get(
        f"/api/controltower/exposure?opportunity_id={opp_id}",
        headers=headers,
    ).json()

    assert exposure["submitted_minor"] == 250000
    assert exposure["certified_minor"] == 125000
    assert exposure["rejected_minor"] == 50000
    assert exposure["unnotified_change_minor"] == 100000
    assert exposure["contract_value_minor"] == 1_000_000
    assert exposure["at_risk_revenue_minor"] == 875000
    assert exposure["age_days_avg"] >= 0
    assert exposure["age_days_max"] >= 0
    assert "cash_exposure_minor" in exposure


def test_dashboard_returns_deadlines_evidence_health_and_unclaimed_events(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)

    client.post(
        f"/api/change/events/{event_id}/evidence",
        json={
            "record_type": "geotagged_photo",
            "title": "Site photo with GPS",
            "metadata": {"geolocation": {"lat": 12.97, "lng": 77.59}},
        },
        headers=headers,
    ).raise_for_status()

    dashboard = client.get(
        f"/api/controltower/dashboard?opportunity_id={opp_id}",
        headers=headers,
    ).json()

    assert len(dashboard["deadlines"]) > 0
    assert "evidence_health_score" in dashboard
    assert dashboard["evidence_health_score"] >= 0
    assert any(
        e["id"] == event_id for e in dashboard["unclaimed_change_events"]
    )


def test_portfolio_rollup_aggregates_exposure_and_health(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)

    submitted = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Submitted claim",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
            "claim_amount_minor": 100000,
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/claims/claims/{submitted['id']}/submit",
        headers=headers,
    ).raise_for_status()

    portfolio = client.get("/api/controltower/portfolio", headers=headers).json()

    assert portfolio["opportunities_count"] >= 1
    assert portfolio["total_submitted_minor"] == 100000
    assert portfolio["total_contract_value_minor"] == 1_000_000
    health_total = (
        portfolio["opportunities_healthy"]
        + portfolio["opportunities_at_risk"]
        + portfolio["opportunities_poor"]
    )
    assert health_total >= 1


def test_forecast_computes_risk_adjusted_cost_and_revenue(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)

    claim = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Forecast claim",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
            "claim_amount_minor": 200_000,
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/claims/claims/{claim['id']}/submit",
        headers=headers,
    ).raise_for_status()

    forecast = client.post(
        "/api/controltower/forecast",
        json={
            "opportunity_id": opp_id,
            "projected_final_cost_minor": 800_000,
            "contingency_percent": 10.0,
            "cost_of_capital_pa": 0.12,
            "currency": "INR",
        },
        headers=headers,
    ).json()

    assert forecast["opportunity_id"] == opp_id
    assert forecast["forecast_revenue_minor"] == 800_000
    assert forecast["forecast_cost_minor"] >= 880_000
    assert forecast["forecast_margin_minor"] is not None
    assert forecast["assumptions"]["projected_final_cost_minor"] == 800_000


def test_response_times_and_negotiation_cadence(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)

    claim = client.post(
        f"/api/claims/opportunities/{opp_id}/claims",
        json={
            "claim_type": "variation",
            "title": "Response claim",
            "change_event_id": event_id,
            "baseline_id": baseline_id,
            "claim_amount_minor": 100_000,
        },
        headers=headers,
    ).json()
    client.post(
        f"/api/claims/claims/{claim['id']}/submit",
        headers=headers,
    ).raise_for_status()

    client.post(
        f"/api/claims/claims/{claim['id']}/responses",
        json={
            "response_kind": "acknowledgment",
            "received_at": "2030-01-01",
            "responder": "Engineer",
            "due_at": "2029-12-15",
        },
        headers=headers,
    ).raise_for_status()

    client.post(
        f"/api/claims/claims/{claim['id']}/negotiations",
        json={
            "offered_amount_minor": 80_000,
            "counter_amount_minor": 90_000,
            "status": "open",
        },
        headers=headers,
    ).raise_for_status()
    client.post(
        f"/api/claims/claims/{claim['id']}/negotiations",
        json={
            "offered_amount_minor": 90_000,
            "counter_amount_minor": 95_000,
            "status": "open",
        },
        headers=headers,
    ).raise_for_status()

    response = client.get(
        f"/api/controltower/response-times?opportunity_id={opp_id}",
        headers=headers,
    ).json()

    assert response["opportunity_id"] == opp_id
    assert response["overall"]["count"] == 1
    assert response["negotiation_cadence_days"] >= 0
    assert any(s["responder"] == "Engineer" for s in response["response_stats"])


def test_clause_trends_and_loss_reasons(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)

    findings = client.get(
        f"/api/review/opportunities/{opp_id}/queue", headers=headers
    ).json()["findings"]
    for i, finding in enumerate(findings):
        client.post(
            f"/api/review/findings/{finding['id']}",
            json={
                "opportunity_id": opp_id,
                "decision": "rejected" if i == 0 else "accepted",
                "review_reason": "not_in_contract" if i == 0 else None,
            },
            headers=headers,
        ).raise_for_status()

    trends = client.get("/api/controltower/clause-trends", headers=headers).json()

    assert trends["workspace_id"]
    assert any(t["count"] > 0 for t in trends["by_category"])
    assert any(lr["reason"] == "not_in_contract" for lr in trends["loss_reasons"])


def test_executive_summary_includes_top_risks_and_links(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)

    summary = client.get(
        f"/api/controltower/executive-summary?opportunity_id={opp_id}",
        headers=headers,
    ).json()

    assert summary["opportunity_id"] == opp_id
    assert summary["exposure"]["contract_value_minor"] == 1_000_000
    assert summary["forecast"] is not None
    assert summary["forecast"]["assumptions"]["contract_value_minor"] == 1_000_000
    assert "top_risks" in summary


def test_payment_schedule_tracks_variance_ageing_and_actions(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)

    client.post(
        "/api/controltower/payment-schedule",
        json={
            "opportunity_id": opp_id,
            "kind": "progress",
            "due_date": "2026-01-01",
            "amount_minor": 500_000,
            "currency": "INR",
        },
        headers=headers,
    ).raise_for_status()

    client.post(
        "/api/controltower/payment-schedule",
        json={
            "opportunity_id": opp_id,
            "kind": "retention",
            "due_date": "2026-08-15",
            "amount_minor": 100_000,
            "certified_amount_minor": 100_000,
            "status": "certified",
            "currency": "INR",
        },
        headers=headers,
    ).raise_for_status()

    schedule = client.get(
        f"/api/controltower/payment-schedule?opportunity_id={opp_id}",
        headers=headers,
    ).json()

    assert schedule["opportunity_id"] == opp_id
    assert len(schedule["schedule"]) == 2
    assert schedule["total_pending_minor"] == 500_000
    assert any(item["variance_minor"] == 500_000 for item in schedule["schedule"])
    assert len(schedule["collection_actions"]) == 1
    assert len(schedule["release_actions"]) == 1


def test_economics_returns_explicit_metrics(client):
    headers = _auth(client)

    economics = client.get(
        "/api/controltower/economics",
        params={
            "cost_of_sales_minor": 100_000,
            "customer_acquisition_cost_minor": 500_000,
            "currency": "INR",
        },
        headers=headers,
    ).json()

    assert "paid_conversion_percent" in economics
    assert economics["cost_of_sales_minor"] == 100_000
    assert economics["customer_acquisition_cost_minor"] == 500_000
    assert "assumptions" in economics


def test_customer_outcomes_aggregates_bids_and_materializations(client):
    headers = _auth(client)
    opp_id, event_id, baseline_id = _setup_project(client, headers)

    client.post(
        f"/api/outcomes/opportunities/{opp_id}",
        json={
            "result": "declined",
            "quoted_value_minor": 2_000_000,
            "currency": "INR",
            "decline_reason": "price_too_high",
        },
        headers=headers,
    ).raise_for_status()

    finding = client.get(
        f"/api/review/opportunities/{opp_id}/queue", headers=headers
    ).json()["findings"][0]
    client.post(
        f"/api/outcomes/findings/{finding['id']}/materialized",
        json={
            "opportunity_id": opp_id,
            "materialized": False,
            "impact_amount_minor": 500_000,
            "currency": "INR",
        },
        headers=headers,
    ).raise_for_status()

    outcomes = client.get(
        "/api/controltower/customer-outcomes",
        headers=headers,
    ).json()

    assert outcomes["workspace_id"]
    assert outcomes["bad_bids_declined_count"] >= 1
    assert outcomes["bad_bids_value_minor"] >= 2_000_000
    assert outcomes["omissions_corrected_count"] >= 1
    assert outcomes["omissions_corrected_value_minor"] >= 500_000
    assert outcomes["hours_saved"] >= 0
