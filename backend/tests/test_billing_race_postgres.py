"""Race-safety of the free-review grant under real concurrency (R-004 §A.4,
TS-087). SQLite tests are effectively single-threaded against one connection,
so the advisory lock's whole job — stopping two concurrent review starts from
both observing free_review_used=False and both spending the single free
review — can only be proven against a real PostgreSQL server. Requires
TS_TEST_DATABASE_URL like test_rls_postgres.py; skipped unless run with
`-m postgres`.
"""

from __future__ import annotations

import os
import threading
import uuid

import pytest
from sqlalchemy import create_engine, insert, text
from sqlalchemy.orm import sessionmaker

import app.modules.auth.models as auth_models  # noqa: F401
import app.modules.billing.models as billing_models  # noqa: F401
from app.core.db import Base, bind_workspace_context, install_rls_rebinding, rls_statements
from app.modules.auth.models import User, Workspace, WorkspaceMember
from app.modules.billing.plans import PaywallError
from app.modules.billing.service import BillingService

pytestmark = pytest.mark.postgres

PG_URL = os.environ.get(
    "TS_TEST_DATABASE_URL",
    "postgresql+psycopg://tendershield:tendershield@localhost:5432/tendershield_rls",
)


@pytest.fixture
def pg_engine():
    engine = create_engine(PG_URL, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"PostgreSQL not reachable at {PG_URL}: {exc}")

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY"))
        conn.execute(text("ALTER TABLE workspaces FORCE ROW LEVEL SECURITY"))
        conn.execute(
            text(
                "CREATE POLICY workspace_isolation ON workspaces USING "
                "(id = NULLIF(current_setting('app.workspace_id', true), '')::uuid) "
                "WITH CHECK (id = NULLIF(current_setting('app.workspace_id', true), '')::uuid)"
            )
        )
        for stmt in rls_statements("usage_events"):
            conn.execute(text(stmt))
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


class _FakeWorkspaceFactory:
    """Mirrors auth.workspace_factory (WorkspaceAdmin) without importing
    auth's service layer — this test only needs get/mark_free_review_used."""

    def __init__(self, session):
        self.s = session

    def get(self, workspace_id):
        from sqlalchemy import select

        return self.s.scalar(select(Workspace).where(Workspace.id == uuid.UUID(str(workspace_id))))

    def mark_free_review_used(self, workspace_id) -> None:
        ws = self.get(workspace_id)
        if ws:
            ws.free_review_used = True

    def set_plan(self, workspace_id, plan: str) -> None:
        ws = self.get(workspace_id)
        if ws:
            ws.plan = plan


def test_concurrent_free_review_grants_exactly_one(pg_engine):
    """Two threads, two real Postgres connections, racing to spend the same
    workspace's single free review. Without the pg_advisory_xact_lock in
    BillingService._lock, both could observe free_review_used=False before
    either commits and both would succeed — this is the test that would have
    caught that."""
    owner_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    factory = sessionmaker(bind=pg_engine, expire_on_commit=False, future=True)
    install_rls_rebinding(factory)

    with pg_engine.begin() as conn:
        conn.execute(
            insert(User),
            [{"id": owner_id, "email": f"{owner_id}@example.com", "email_verified": False,
              "is_superadmin": False, "mfa_method": "totp"}],
        )
    # workspaces/usage_events are FORCE RLS now — bind to the new workspace's
    # own id before inserting it, same as AuthService._create_workspace_and_owner.
    seed = factory()
    try:
        bind_workspace_context(seed, workspace_id)
        seed.execute(
            insert(Workspace),
            [{"id": workspace_id, "owner_id": owner_id, "name": "Race Co", "country": "IN",
              "plan": "free", "free_review_used": False}],
        )
        seed.execute(
            insert(WorkspaceMember),
            [{"workspace_id": workspace_id, "user_id": owner_id, "role": "owner"}],
        )
        seed.commit()
    finally:
        seed.close()

    barrier = threading.Barrier(2)
    results: list[str] = []
    lock = threading.Lock()

    def attempt():
        session = factory()
        try:
            bind_workspace_context(session, workspace_id)
            svc = BillingService(session, workspace_factory=lambda s: _FakeWorkspaceFactory(s))
            barrier.wait(timeout=5)  # line both threads up before racing
            try:
                grant = svc.authorize_review(workspace_id, opportunity_id=None)
                with lock:
                    results.append(grant.kind)
            except PaywallError as exc:
                with lock:
                    results.append(f"blocked:{exc.code}")
        finally:
            session.close()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(results) == 2
    granted = [r for r in results if r == "free_first_review"]
    blocked = [r for r in results if r == "blocked:free_exhausted"]
    assert len(granted) == 1, f"expected exactly one grant, got {results}"
    assert len(blocked) == 1, f"expected exactly one block, got {results}"
