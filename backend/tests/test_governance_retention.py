"""Governance retention job integration tests (TS-340)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.ingestion.models import Document, Opportunity
from tests.helpers import auth_headers_and_workspace

MODULES = "health,rulepacks,auth,ingestion,findings,risk,review,governance"


@pytest.fixture
def client():
    app = create_app(
        Settings(
            enabled_modules=MODULES,
            database_url="sqlite:///:memory:",
            storage_type="local",
            storage_dir=".tender_storage_test",
            retention_job_enabled=True,
            retention_grace_days=30,
        )
    )
    Base.metadata.create_all(app.state.ctx.registry.require("db.engine"))
    return TestClient(app)


@pytest.fixture
def session(client):
    Session = client.app.state.ctx.registry.require("db.sessionmaker")
    return Session()


def _workspace_and_opportunity(client, session):
    headers, workspace_id = auth_headers_and_workspace(client, "retention@example.com")
    opp = Opportunity(
        workspace_id=uuid.UUID(workspace_id),
        title="Retention Test",
        jurisdiction="IN",
    )
    session.add(opp)
    session.commit()
    session.refresh(opp)
    return headers, workspace_id, str(opp.id)




def _make_document(
    session,
    workspace_id,
    opportunity_id,
    *,
    days_old,
    archived_at=None,
    deleted_at=None,
):
    doc = Document(
        workspace_id=uuid.UUID(workspace_id),
        opportunity_id=uuid.UUID(opportunity_id),
        filename="old.pdf",
        kind="nit",
        s3_key=f"workspace/{workspace_id}/old.pdf",
        sha256="deadbeef",
        created_at=datetime.now(UTC) - timedelta(days=days_old),
        archived_at=archived_at,
        deleted_at=deleted_at,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return str(doc.id)


def _governance_service(client, session):
    from app.core.storage import get_storage
    from app.modules.governance.service import GovernanceService

    reg = client.app.state.ctx.registry

    return GovernanceService(
        session,
        ingestion_retention=reg.get("ingestion.documents_for_retention"),
        ingestion_apply=reg.get("ingestion.retention_apply"),
        review_factory=reg.get("review.service_factory"),
        storage=get_storage(client.app.state.ctx.settings),
        settings=client.app.state.ctx.settings,
        publish=client.app.state.ctx.events.publish,
    )


def test_retention_job_disabled_by_default(client, session):
    svc = _governance_service(client, session)
    svc._settings = Settings(retention_job_enabled=False)
    result = asyncio.run(svc.run_retention_job())
    assert result["enabled"] is False


def test_retention_job_archives_and_soft_deletes(client, session):
    headers, workspace_id, opportunity_id = _workspace_and_opportunity(client, session)

    # Configure: archive at 90 days, delete at 180 days.
    r = client.put(
        f"/api/governance/workspaces/{workspace_id}/data-governance",
        json={"retention_days": 180, "archive_after_days": 90},
        headers=headers,
    )
    assert r.status_code == 200

    # Doc is 100 days old -> should be archived, not yet deleted.
    doc_id = _make_document(session, workspace_id, opportunity_id, days_old=100)

    now = datetime.now(UTC) - timedelta(days=0)
    result = asyncio.run(_governance_service(client, session).run_retention_job(now=now))
    assert result["enabled"] is True
    assert result["workspaces_scanned"] == 1
    assert result["archived"] == 1
    assert result["soft_deleted"] == 0
    assert result["hard_deleted"] == 0

    # Verify archived_at is set and storage key still reachable.
    from sqlalchemy import select

    doc = session.scalar(select(Document).where(Document.id == uuid.UUID(doc_id)))
    assert doc.archived_at is not None
    assert doc.deleted_at is None


def test_retention_job_soft_deletes_then_hard_deletes(client, session):
    headers, workspace_id, opportunity_id = _workspace_and_opportunity(client, session)

    r = client.put(
        f"/api/governance/workspaces/{workspace_id}/data-governance",
        json={"retention_days": 180},
        headers=headers,
    )
    assert r.status_code == 200

    # Document is 200 days old -> soft delete first.
    _make_document(session, workspace_id, opportunity_id, days_old=200)
    first_run = datetime.now(UTC)
    result = asyncio.run(_governance_service(client, session).run_retention_job(now=first_run))
    assert result["soft_deleted"] == 1
    assert result["hard_deleted"] == 0

    # Advance time beyond the 30-day grace period; hard delete on next run.
    second_run = first_run + timedelta(days=31)
    result = asyncio.run(_governance_service(client, session).run_retention_job(now=second_run))
    assert result["hard_deleted"] == 1

    from sqlalchemy import select

    assert (
        session.scalar(select(Document).where(Document.workspace_id == uuid.UUID(workspace_id)))
        is None
    )


def test_retention_job_skips_legal_hold(client, session):
    headers, workspace_id, opportunity_id = _workspace_and_opportunity(client, session)

    r = client.put(
        f"/api/governance/workspaces/{workspace_id}/data-governance",
        json={"retention_days": 180, "legal_hold": True},
        headers=headers,
    )
    assert r.status_code == 200

    _make_document(session, workspace_id, opportunity_id, days_old=200)
    result = asyncio.run(_governance_service(client, session).run_retention_job())
    assert result["workspaces_scanned"] == 0

