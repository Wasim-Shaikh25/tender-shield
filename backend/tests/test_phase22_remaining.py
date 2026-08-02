"""Phase 22 backend integration tests for TS-317, TS-318, TS-319, TS-309, TS-320."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.comparison.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.integrations.models  # noqa: F401
import app.modules.outcomes.models  # noqa: F401
import app.modules.pricing.models  # noqa: F401
import app.modules.standards.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = (
    "health,rulepacks,auth,ingestion,findings,risk,review,boq,baseline,change,"
    "outcomes,comparison,standards,pricing,integrations"
)

BOQ_CSV = (
    "src_row,description,unit_raw,qty,rate,amount\n"
    "1,Concrete in footing,cum,10,5000,50000\n"
    "2,Steel reinforcement,kg,1000,60,60000\n"
)


@pytest.fixture
def client():
    app = create_app(Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:"))
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    return auth_headers(client, "phase22@x.com")


def _opp_ready(client, headers, text: str):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Phase22 OPP"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "gcc.pdf", "sample_text": text},
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
    return opp_id


def test_deviation_report_against_commercial_standard_ts317(client):
    """TS-317: clause deviation scoring flags policy violations."""
    headers = _auth(client)
    text = "[p1]\nClause 42 — Liquidated damages shall be 10% of contract value.\n"
    opp_id = _opp_ready(client, headers, text)

    policy = {
        "label": "LD cap",
        "operator": "gt",
        "threshold": 5,
        "unit": "percent",
        "applies_to": ["liquidated", "ld"],
    }
    r = client.put("/api/standards/commercial/ld_cap", json=policy, headers=headers)
    assert r.status_code == 200, r.text

    report = client.get(
        f"/api/comparison/opportunities/{opp_id}/deviation", headers=headers
    ).json()
    assert report["policies_checked"] >= 1
    assert any(v["policy_key"] == "ld_cap" for c in report["clauses"] for v in c["violations"])


def test_boq_schedule_cross_check_and_historical_patterns_ts318_ts319(client):
    """TS-318/TS-319: BOQ cross-check with imported schedule and historical scope patterns."""
    headers = _auth(client)
    opp1 = _opp_ready(
        client,
        headers,
        "[p1]\nClause 1 — Concrete works and excavation.\n",
    )

    schedule_csv = (
        "activity_id,name,start,finish,duration_days\n"
        "P01,Piling works,2026-08-01,2026-08-10,10\n"
    )
    client.post(
        f"/api/integrations/schedule/opportunities/{opp1}/upload",
        files={"file": ("schedule.csv", schedule_csv.encode(), "text/csv")},
        headers=headers,
    )
    run = client.post(
        f"/api/boq/opportunities/{opp1}/run",
        json={"csv": BOQ_CSV},
        headers=headers,
    )
    assert run.status_code == 200, run.text
    findings = run.json()["findings"]
    assert any(f["category"] == "schedule_mismatch" for f in findings)

    opp2 = client.post(
        "/api/ingestion/opportunities", json={"title": "Patterns OPP"}, headers=headers
    ).json()["id"]
    patterns = client.get(
        f"/api/outcomes/opportunities/{opp2}/scope-patterns", headers=headers
    ).json()
    assert any(p["category"] == "schedule_mismatch" for p in patterns["patterns"])

    run2 = client.post(
        f"/api/boq/opportunities/{opp2}/run",
        json={"csv": BOQ_CSV},
        headers=headers,
    )
    assert run2.status_code == 200, run2.text
    assert any("historical:" in f["category"] for f in run2.json()["findings"])


def test_rate_benchmark_buildup_and_sensitivity_ts309_ts320(client):
    """TS-309/TS-320: rate benchmark, build-up, and sensitivity endpoints."""
    headers = _auth(client)
    opp_id = _opp_ready(
        client,
        headers,
        "[p1]\nClause 12 — Variations require 14 days notice.\n",
    )

    bench = client.post(
        f"/api/pricing/opportunities/{opp_id}/rate-benchmark",
        json={"csv": BOQ_CSV, "authority": "cpwd", "year": "2025"},
        headers=headers,
    )
    assert bench.status_code == 200, bench.text
    body = bench.json()
    assert "unmatched" in body
    assert isinstance(body["code_matched"], list)

    buildup = client.post(
        f"/api/pricing/opportunities/{opp_id}/rate-buildup",
        json={"csv": BOQ_CSV, "currency": "INR"},
        headers=headers,
    )
    assert buildup.status_code == 200, buildup.text
    assert buildup.json()["total_amount_minor"] > 0
    assert any(i["material_rate_minor"] > 0 for i in buildup.json()["items"])

    sens = client.post(
        f"/api/pricing/opportunities/{opp_id}/sensitivity",
        json={
            "csv": BOQ_CSV,
            "currency": "INR",
            "scenarios": [{"name": "Rates +10", "param": "rate", "delta_pct": 10}],
        },
        headers=headers,
    )
    assert sens.status_code == 200, sens.text
    assert len(sens.json()["scenarios"]) >= 1
