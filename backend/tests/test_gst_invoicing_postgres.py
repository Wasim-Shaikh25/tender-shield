"""Gap-free invoice numbering under real concurrency (R-007 §B.3, A5).
SQLite tests are effectively single-threaded against one connection, so the
`SELECT ... FOR UPDATE` serialization in BillingService._next_seq can only be
proven against a real, non-superuser PostgreSQL server with two genuine
threads — mirrors test_billing_race_postgres.py's pattern.
"""

from __future__ import annotations

import os
import threading
import types
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.orm import sessionmaker

import app.modules.auth.models as auth_models  # noqa: F401
import app.modules.billing.models as billing_models  # noqa: F401
from app.core.db import Base, bind_workspace_context, install_rls_rebinding, rls_statements
from app.modules.auth.models import User, Workspace, WorkspaceMember
from app.modules.billing.models import Invoice, InvoiceSequence, PaymentIntent
from app.modules.billing.providers.base import ProviderEvent
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
        for stmt in rls_statements("invoices"):
            conn.execute(text(stmt))
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


class _FakeWorkspaceFactory:
    def __init__(self, session):
        self.s = session

    def get(self, workspace_id):
        return self.s.scalar(select(Workspace).where(Workspace.id == uuid.UUID(str(workspace_id))))


def test_concurrent_invoice_issuance_produces_no_duplicate_sequence_numbers(pg_engine):
    """Two threads issuing an invoice for the SAME financial year at the same
    time must not receive the same seq — `_next_seq`'s `SELECT ... FOR UPDATE`
    is what serializes this; without it, both transactions could read
    last_seq=0 and both write seq=1."""
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
    seed = factory()
    try:
        bind_workspace_context(seed, workspace_id)
        seed.execute(
            insert(Workspace),
            [{"id": workspace_id, "owner_id": owner_id, "name": "Race Co", "country": "IN",
              "plan": "pro"}],
        )
        seed.execute(
            insert(WorkspaceMember),
            [{"workspace_id": workspace_id, "user_id": owner_id, "role": "owner"}],
        )
        seed.commit()
    finally:
        seed.close()

    settings = types.SimpleNamespace(
        invoice_series_prefix="TS", seller_state_code="27", seller_gstin="27AAAAA0000A1Z5"
    )
    barrier = threading.Barrier(2)
    results: list[Invoice] = []
    lock = threading.Lock()

    def issue_one(idx: int):
        session = factory()
        try:
            bind_workspace_context(session, workspace_id)
            svc = BillingService(
                session, workspace_factory=lambda s: _FakeWorkspaceFactory(s), settings=settings
            )
            intent = PaymentIntent(
                id=uuid.uuid4(), workspace_id=workspace_id, kind="paygo", plan="paygo",
                list_amount_minor=750_000, amount_minor=750_000, currency="INR",
                provider="razorpay", idempotency_key=f"race-{idx}",
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
            )
            session.add(intent)
            session.flush()
            event = ProviderEvent(
                provider="razorpay", event_id=f"evt-{idx}", type="order.paid",
                amount_minor=750_000, currency="INR", reference_id=str(intent.id), raw={},
            )
            barrier.wait(timeout=5)
            inv = svc.issue_invoice(intent, event)
            session.commit()
            with lock:
                results.append(inv)
        finally:
            session.close()

    threads = [threading.Thread(target=issue_one, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(results) == 2
    seqs = sorted(inv.seq for inv in results)
    assert seqs == [1, 2], f"expected consecutive seqs [1, 2], got {seqs}"
    numbers = {inv.invoice_number for inv in results}
    assert len(numbers) == 2  # no duplicate invoice numbers either

    with factory() as check:
        row = check.scalar(select(InvoiceSequence))
        assert row.last_seq == 2
