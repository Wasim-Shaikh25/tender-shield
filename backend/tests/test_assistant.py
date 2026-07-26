"""Assistant: grounded deterministic intents (no LLM key) + off-topic refusal."""

import pytest
from fastapi.testclient import TestClient

import app.modules.assistant.models  # noqa: F401
import app.modules.auth.models  # noqa: F401
import app.modules.findings.models  # noqa: F401
import app.modules.ingestion.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules="health,rulepacks,auth,ingestion,findings,risk,assistant",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


def _auth(client):
    client.post(
        "/api/auth/signup",
        json={"email": "as@x.com", "password": "hunter2hunter2", "workspace_name": "Acme"},
    )
    tok = client.post(
        "/api/auth/login", json={"email": "as@x.com", "password": "hunter2hunter2"}
    ).json()["access_token"]
    return {"authorization": f"Bearer {tok}"}


def _opp(client, headers):
    opp_id = client.post(
        "/api/ingestion/opportunities", json={"title": "Metro"}, headers=headers
    ).json()["id"]
    nit = (
        "[p1]\nNOTICE INVITING TENDER No. 7\n"
        "Last date of submission of bid: 25/08/2026.\n"
        "Clause 5 — Scope. Build a depot.\n"
    )
    client.post(
        f"/api/ingestion/opportunities/{opp_id}/documents",
        json={"filename": "nit.pdf", "sample_text": nit},
        headers=headers,
    )
    client.post(f"/api/risk/opportunities/{opp_id}/run", headers=headers)
    return opp_id


def _ask(client, headers, opp_id, message):
    return client.post(
        "/api/assistant/chat", json={"opportunity_id": opp_id, "message": message}, headers=headers
    ).json()


def test_deadline_intent_is_grounded_with_citation(client):
    headers = _auth(client)
    opp_id = _opp(client, headers)
    ans = _ask(client, headers, opp_id, "list the deadlines")
    assert ans["source"] == "tool"
    assert "submission" in ans["answer"]
    assert "[p1]" in ans["answer"]


def test_findings_intent(client):
    headers = _auth(client)
    opp_id = _opp(client, headers)
    ans = _ask(client, headers, opp_id, "show me the risk findings")
    assert ans["source"] == "tool"
    # escalation absence finding fires on this no-escalation tender
    assert "escalation" in ans["answer"].lower()


def test_missing_docs_intent(client):
    headers = _auth(client)
    opp_id = _opp(client, headers)
    ans = _ask(client, headers, opp_id, "which documents are missing?")
    assert "GCC" in ans["answer"] or "BOQ" in ans["answer"]


def test_offtopic_is_refused(client):
    headers = _auth(client)
    opp_id = _opp(client, headers)
    ans = _ask(client, headers, opp_id, "what's the weather in Mumbai today?")
    assert ans["source"] == "refusal"


def test_session_and_history(client):
    headers = _auth(client)
    opp_id = _opp(client, headers)

    s = client.post(
        "/api/assistant/sessions",
        json={"opportunity_id": opp_id, "title": "Risk chat"},
        headers=headers,
    ).json()
    session_id = s["id"]
    assert s["opportunity_id"] == opp_id

    ans = client.post(
        f"/api/assistant/sessions/{session_id}/chat",
        json={"message": "show me the risk findings"},
        headers=headers,
    ).json()
    assert ans["source"] == "tool"

    msgs = client.get(f"/api/assistant/sessions/{session_id}/messages", headers=headers).json()[
        "messages"
    ]
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == ans["answer"]


def test_sse_stream_stores_messages(client):
    headers = _auth(client)
    opp_id = _opp(client, headers)
    s = client.post(
        "/api/assistant/sessions",
        json={"opportunity_id": opp_id},
        headers=headers,
    ).json()
    session_id = s["id"]

    r = client.post(
        f"/api/assistant/sessions/{session_id}/stream",
        json={"message": "list the deadlines"},
        headers=headers,
    )
    assert r.headers["content-type"].startswith("text/event-stream")
    # stream contains at least one data line
    assert b"data:" in r.content

    msgs = client.get(f"/api/assistant/sessions/{session_id}/messages", headers=headers).json()[
        "messages"
    ]
    assert len(msgs) == 2
