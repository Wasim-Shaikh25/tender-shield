"""Approval matrix tests (TS-239)."""

import uuid

import pytest
from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
import app.modules.baseline.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.auth.approval import ApprovalMatrix
from app.modules.baseline.service import BaselineError, BaselineService
from tests.helpers import auth_headers_and_workspace

MODULES = "health,rulepacks,auth,ingestion,findings,risk,review,standards,baseline"


@pytest.fixture
def client():
    application = create_app(Settings(enabled_modules=MODULES, database_url="sqlite:///:memory:"))
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def test_approval_matrix_denies_role_below_minimum(client):
    headers, workspace_id = auth_headers_and_workspace(client, "matrix@example.com")
    client.put(
        f"/api/auth/workspaces/{workspace_id}/approval-matrix",
        headers=headers,
        json={"limits": [{"action": "watchlist_edit", "min_role": "admin"}]},
    ).raise_for_status()

    Session = client.app.state.ctx.registry.require("db.sessionmaker")
    with Session() as session:
        matrix = ApprovalMatrix(session)
        decision = matrix.check(workspace_id, role="estimator", action="watchlist_edit")
        assert not decision.allowed
        assert decision.reason == "role_below_minimum"


def test_approval_matrix_allows_when_action_not_configured(client):
    headers, workspace_id = auth_headers_and_workspace(client, "open@example.com")
    Session = client.app.state.ctx.registry.require("db.sessionmaker")
    with Session() as session:
        matrix = ApprovalMatrix(session)
        decision = matrix.check(workspace_id, role="viewer", action="watchlist_edit")
        assert decision.allowed


def test_baseline_service_blocks_watchlist_edit_when_matrix_requires_admin(client):
    headers, workspace_id = auth_headers_and_workspace(client, "baseline-matrix@example.com")
    client.put(
        f"/api/auth/workspaces/{workspace_id}/approval-matrix",
        headers=headers,
        json={"limits": [{"action": "watchlist_edit", "min_role": "admin"}]},
    ).raise_for_status()

    reg = client.app.state.ctx.registry
    Session = reg.require("db.sessionmaker")

    def factory(session):
        return BaselineService(
            session,
            approval_matrix_factory=reg.get("auth.approval_matrix"),
        )

    with Session() as session:
        svc = factory(session)
        with pytest.raises(BaselineError) as exc:
            svc.update_watchlist(
                workspace_id,
                str(uuid.uuid4()),
                actor_role="estimator",
            )
        assert exc.value.code == "approval_denied"
