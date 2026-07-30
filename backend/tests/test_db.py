import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import Settings
from app.core.db import (
    WORKSPACE_SCOPED_TABLES,
    Base,
    TimestampMixin,
    WorkspaceScopedMixin,
    bind_workspace_context,
    make_engine,
    make_session_factory,
    rls_statements,
)


class _SampleRow(Base, WorkspaceScopedMixin, TimestampMixin):
    _tablename_ = "sample_rows"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String)


def test_org_scoped_table_registered_for_rls():
    assert "sample_rows" in WORKSPACE_SCOPED_TABLES
    assert "workspace_members" in WORKSPACE_SCOPED_TABLES
    assert "project_members" in WORKSPACE_SCOPED_TABLES


def test_rls_statements_shape():
    stmts = rls_statements("findings")
    assert stmts[0] == "ALTER TABLE findings ENABLE ROW LEVEL SECURITY"
    assert stmts[1] == "ALTER TABLE findings FORCE ROW LEVEL SECURITY"
    assert "current_setting('app.workspace_id', true)::uuid" in stmts[2]
    assert "WITH CHECK" in stmts[2]
    assert "CREATE POLICY workspace_isolation ON findings" in stmts[2]


def test_session_roundtrip_on_sqlite():
    engine = make_engine(Settings(database_url="sqlite+pysqlite:///:memory:"))
    Base.metadata.create_all(engine, tables=[_SampleRow.__table__])
    factory = make_session_factory(engine)
    org = uuid.uuid4()
    with factory() as session:
        # bind_workspace_context is a no-op on SQLite but must not raise (spec B1 path)
        bind_workspace_context(session, org)
        session.add(_SampleRow(id=uuid.uuid4(), workspace_id=org, label="hi"))
        session.commit()
    with factory() as session:
        rows = session.query(_SampleRow).all()
        assert len(rows) == 1
        assert rows[0].workspace_id == org
        assert rows[0].created_at is not None


def test_app_publishes_db_capabilities():
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(Settings(enabled_modules="health", database_url="sqlite:///:memory:"))
    caps = TestClient(app).get("/api/health/details").json()["capabilities"]
    assert "db.engine" in caps
    assert "db.sessionmaker" in caps
