"""Correction loop tests (TS-218)."""

import uuid

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
import app.modules.rulepacks.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.rulepacks.corrections import (
    PatternFamilyStats,
    aggregate_pattern_stats,
    suggest_overlay,
)
from tests.helpers import auth_headers


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules="health,rulepacks,auth,ingestion,findings,risk,review",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def test_suggest_overlay_requires_minimum_reviews():
    low = PatternFamilyStats("p1", "NHAI", 4, 0, 0, 2, 2)
    assert suggest_overlay(low) is None


def test_suggest_overlay_on_high_false_positive_rate():
    high = PatternFamilyStats("liquidated_damages_uncapped", "NHAI", 8, 1, 0, 2, 5)
    overlay = suggest_overlay(high)
    assert overlay is not None
    assert overlay["pattern_id"] == "liquidated_damages_uncapped"
    assert "PROPOSED" in overlay["disclaimer"]


def test_aggregate_groups_by_pattern_and_family():
    opp_a = uuid.uuid4()
    opp_b = uuid.uuid4()

    class Row:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    findings = [
        Row(
            pattern_id="p1",
            opportunity_id=opp_a,
            review_status="false_positive",
        ),
        Row(
            pattern_id="p1",
            opportunity_id=opp_a,
            review_status="rejected",
        ),
        Row(
            pattern_id="p1",
            opportunity_id=opp_b,
            review_status="accepted",
        ),
    ]
    stats = aggregate_pattern_stats(
        findings,
        family_for_opportunity={str(opp_a): "NHAI", str(opp_b): "CPWD"},
    )
    assert len(stats) == 2
    nhai = next(s for s in stats if s.employer_family == "NHAI")
    assert nhai.false_positive == 1
    assert nhai.rejected == 1


def test_correction_scan_creates_proposal(client):
    headers = auth_headers(client, "corr@example.com")
    opp_id = client.post(
        "/api/ingestion/opportunities",
        json={"title": "NHAI bridge", "employer_family": "NHAI"},
        headers=headers,
    ).json()["id"]

    from sqlalchemy.orm import Session

    from app.modules.findings.models import FindingRow

    ws_id = client.get("/api/auth/me", headers=headers).json()["workspace_id"]
    pattern_id = "liquidated_damages_uncapped"
    engine = client.app.state.ctx.registry.require("db.engine")
    with Session(engine) as session:
        for i in range(7):
            session.add(
                FindingRow(
                    workspace_id=uuid.UUID(ws_id),
                    opportunity_id=uuid.UUID(opp_id),
                    producer="risk",
                    kind="risk_clause",
                    category="payment",
                    severity="high",
                    title=f"finding {i}",
                    detail="",
                    source="test",
                    pattern_id=pattern_id,
                    review_status="false_positive",
                )
            )
        session.commit()

    scan = client.post("/api/rulepacks/corrections/scan", headers=headers)
    assert scan.status_code == 200
    assert scan.json()["proposals_created"] >= 1

    proposals = client.get("/api/rulepacks/corrections/proposals", headers=headers).json()
    assert proposals["proposals"]
    assert proposals["proposals"][0]["status"] == "proposed"
    assert "PROPOSED" in proposals["proposals"][0]["overlay"]["disclaimer"]

    dismiss = client.post(
        f"/api/rulepacks/corrections/proposals/{proposals['proposals'][0]['id']}/dismiss",
        headers=headers,
    )
    assert dismiss.status_code == 200
    assert dismiss.json()["status"] == "dismissed"
