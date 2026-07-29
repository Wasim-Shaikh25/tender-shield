"""Organization Standards enforcement (TS-056):
- CRUD for commercial policy thresholds (admin).
- Violation detection against accepted findings (qualification in this test).
- Persisted `standard_violation` findings when a policy is breached.
- `bid_decision` consumes those violations through the findings store."""

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.review.models  # noqa: F401
import app.modules.standards.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules=(
                "health,rulepacks,auth,ingestion,findings,risk,review,"
                "standards,qualification,drafting"
            ),
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    client.post(
        "/api/auth/signup",
        json={"email": "st@x.com", "password": "Hunter2!Hunter2", "workspace_name": "Acme"},
    )
    tok = client.post(
        "/api/auth/login", json={"email": "st@x.com", "password": "Hunter2!Hunter2"}
    ).json()["access_token"]
    return {"authorization": f"Bearer {tok}"}


def _opp_with_turnover(client, headers):
    text = "[p1] The bidder shall have a minimum turnover of Rs. 10 Cr in the last three years."
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Road"}, headers=headers
    ).json()["id"]
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "nit.pdf", "sample_text": text},
        headers=headers,
    )
    client.post(f"/api/qualification/opportunities/{opp_id}", headers=headers)
    return opp_id


def test_policy_crud(client):
    headers = _auth(client)
    resp = client.put(
        "/api/standards/commercial/max_turnover_req",
        json={
            "label": "Maximum turnover requirement we can meet",
            "operator": "gt",
            "threshold": 5,
            "unit": "amount",
            "applies_to": ["turnover"],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["threshold"] == 5

    listed = client.get("/api/standards/commercial", headers=headers).json()["policies"]
    assert any(p["key"] == "max_turnover_req" for p in listed)

    assert client.delete("/api/standards/commercial/max_turnover_req", headers=headers).json()[
        "deleted"
    ]


def test_violation_detection_persists_standard_violation(client):
    headers = _auth(client)
    opp_id = _opp_with_turnover(client, headers)

    client.put(
        "/api/standards/commercial/max_turnover_req",
        json={
            "label": "Maximum turnover requirement we can meet",
            "operator": "gt",
            "threshold": 5,
            "unit": "amount",
            "applies_to": ["turnover"],
        },
        headers=headers,
    )

    # accept the qualification finding
    for f in client.get(f"/api/review/opportunities/{opp_id}/queue", headers=headers).json()[
        "findings"
    ]:
        client.post(
            f"/api/review/findings/{f['id']}", json={"decision": "accepted"}, headers=headers
        )

    check = client.post(f"/api/standards/opportunities/{opp_id}/check", headers=headers)
    assert check.status_code == 200
    assert len(check.json()["violations"]) == 1
    assert check.json()["violations"][0]["value"] == 10.0

    findings = client.get(f"/api/findings/opportunities/{opp_id}", headers=headers).json()[
        "findings"
    ]
    standard_findings = [f for f in findings if f["kind"] == "standard_violation"]
    assert len(standard_findings) == 1
    assert "Company standard violated" in standard_findings[0]["title"]


def test_bid_decision_considers_standard_violation(client):
    headers = _auth(client)
    opp_id = _opp_with_turnover(client, headers)

    client.put(
        "/api/standards/commercial/max_turnover_req",
        json={
            "label": "Maximum turnover requirement we can meet",
            "operator": "gt",
            "threshold": 5,
            "unit": "amount",
            "applies_to": ["turnover"],
        },
        headers=headers,
    )

    for f in client.get(f"/api/review/opportunities/{opp_id}/queue", headers=headers).json()[
        "findings"
    ]:
        client.post(
            f"/api/review/findings/{f['id']}", json={"decision": "accepted"}, headers=headers
        )

    client.post(f"/api/standards/opportunities/{opp_id}/check", headers=headers)

    # accept the newly created standard_violation finding
    for f in client.get(f"/api/review/opportunities/{opp_id}/queue", headers=headers).json()[
        "findings"
    ]:
        if f["kind"] == "standard_violation":
            client.post(
                f"/api/review/findings/{f['id']}",
                json={"decision": "accepted"},
                headers=headers,
            )

    decision = client.post(
        f"/api/drafting/opportunities/{opp_id}/artifacts",
        json={"kind": "bid_decision"},
        headers=headers,
    ).json()["body"]
    assert decision["kind"] == "bid_decision"
    assert any("standard" in c["category"].lower() for c in decision["concerns"])
