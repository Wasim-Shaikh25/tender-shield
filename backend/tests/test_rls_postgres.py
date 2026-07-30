"""PostgreSQL-only RLS integration tests (TS-A03).

Skipped unless TS_DATABASE_URL points at PostgreSQL.
Run against a non-superuser role so `FORCE ROW LEVEL SECURITY` is actually exercised.
"""

import os
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import Settings
from app.core.db import (
    Base,
    WorkspaceScopedMixin,
    bind_workspace_context,
    make_engine,
    make_session_factory,
    rls_statements,
)


class _RlsSample(Base, WorkspaceScopedMixin):
    _tablename_ = "rls_samples"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    label: Mapped[str]


def _pg_url():
    url = os.environ.get("TS_DATABASE_URL") or Settings().database_url
    if not url or "postgresql" not in url:
        pytest.skip("PostgreSQL not configured")
    return url


@pytest.fixture(scope="module")
def pg_engine():
    engine = make_engine(Settings(database_url=_pg_url()))
    with engine.begin() as conn:
        _RlsSample.__table__.drop(conn, checkfirst=True)
        _RlsSample.__table__.create(conn)
        for stmt in rls_statements("rls_samples"):
            conn.execute(text(stmt))
    yield engine
    with engine.begin() as conn:
        _RlsSample.__table__.drop(conn, checkfirst=True)


def _factory(engine):
    return make_session_factory(engine)


def test_rls_statements_cover_force_and_with_check():
    stmts = rls_statements("rls_samples")
    assert any("FORCE ROW LEVEL SECURITY" in s for s in stmts)
    assert any("WITH CHECK" in s for s in stmts)
    assert any("nullif(current_setting('app.workspace_id', true), '')::uuid" in s for s in stmts)


def test_rls_blocks_cross_workspace_read(pg_engine):
    factory = _factory(pg_engine)
    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()

    with factory() as s:
        bind_workspace_context(s, ws_a)
        s.add(_RlsSample(id=uuid.uuid4(), workspace_id=ws_a, label="a"))
        s.commit()

    with factory() as s:
        bind_workspace_context(s, ws_b)
        s.add(_RlsSample(id=uuid.uuid4(), workspace_id=ws_b, label="b"))
        s.commit()

    with factory() as s:
        bind_workspace_context(s, ws_a)
        rows = s.scalars(select(_RlsSample)).all()
        assert len(rows) == 1
        assert rows[0].workspace_id == ws_a
        assert rows[0].label == "a"


def test_rls_blocks_cross_workspace_write(pg_engine):
    factory = _factory(pg_engine)
    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()

    with factory() as s:
        bind_workspace_context(s, ws_a)
        s.add(_RlsSample(id=uuid.uuid4(), workspace_id=ws_b, label="x"))
        with pytest.raises(IntegrityError):  # WITH CHECK violation
            s.commit()


def test_unbound_session_reads_no_rows(pg_engine):
    factory = _factory(pg_engine)
    ws_a = uuid.uuid4()

    with factory() as s:
        bind_workspace_context(s, ws_a)
        s.add(_RlsSample(id=uuid.uuid4(), workspace_id=ws_a, label="a"))
        s.commit()

    with factory() as s:
        # No SET LOCAL app.workspace_id; current_setting(..., true) -> nullif -> NULL.
        rows = s.scalars(select(_RlsSample)).all()
        assert rows == []


def test_rls_applies_to_table_owner(pg_engine):
    """The connection role owns the table; FORCE must still enforce the policy."""
    factory = _factory(pg_engine)
    ws_a = uuid.uuid4()

    with factory() as s:
        bind_workspace_context(s, ws_a)
        s.add(_RlsSample(id=uuid.uuid4(), workspace_id=ws_a, label="owner"))
        s.commit()

    with factory() as s:
        bind_workspace_context(s, uuid.uuid4())
        rows = s.scalars(select(_RlsSample)).all()
        assert rows == []
