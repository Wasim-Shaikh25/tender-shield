"""PostgreSQL-only RLS integration tests (TS-A03).

Skipped unless TS_DATABASE_URL points at PostgreSQL.
"""

import os
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
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


@pytest.fixture
def pg_settings():
    url = os.environ.get("TS_DATABASE_URL") or Settings().database_url
    if not url or "postgresql" not in url:
        pytest.skip("PostgreSQL not configured")
    return Settings(database_url=url)


@pytest.fixture
def pg_engine(pg_settings):
    engine = make_engine(pg_settings)
    _RlsSample.metadata.create_all(engine, tables=[_RlsSample.__table__])
    yield engine
    _RlsSample.metadata.drop_all(engine, tables=[_RlsSample.__table__])


def test_rls_statements_cover_force_and_with_check():
    stmts = rls_statements("rls_samples")
    assert any("FORCE ROW LEVEL SECURITY" in s for s in stmts)
    assert any("WITH CHECK" in s for s in stmts)
    assert any("current_setting('app.workspace_id', true)" in s for s in stmts)


def test_rls_blocks_cross_workspace_read(pg_engine):
    factory = make_session_factory(pg_engine)
    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()

    with factory() as s:
        bind_workspace_context(s, ws_a)
        s.add(_RlsSample(id=uuid.uuid4(), workspace_id=ws_a, label="a"))
        s.add(_RlsSample(id=uuid.uuid4(), workspace_id=ws_b, label="b"))
        s.commit()

    with factory() as s:
        bind_workspace_context(s, ws_a)
        rows = s.scalars(select(_RlsSample)).all()
        assert len(rows) == 1
        assert rows[0].workspace_id == ws_a


def test_rls_blocks_cross_workspace_write(pg_engine):
    factory = make_session_factory(pg_engine)
    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()

    with factory() as s:
        bind_workspace_context(s, ws_a)
        s.add(_RlsSample(id=uuid.uuid4(), workspace_id=ws_b, label="x"))
        with pytest.raises(SQLAlchemyError):  # WITH CHECK violation
            s.commit()


def test_unbound_session_reads_no_rows(pg_engine):
    factory = make_session_factory(pg_engine)
    ws_a = uuid.uuid4()

    with factory() as s:
        bind_workspace_context(s, ws_a)
        s.add(_RlsSample(id=uuid.uuid4(), workspace_id=ws_a, label="a"))
        s.commit()

    with factory() as s:
        # No SET LOCAL app.workspace_id; current_setting(..., true) returns NULL.
        rows = s.scalars(select(_RlsSample)).all()
        assert rows == []
