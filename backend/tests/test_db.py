import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import Settings
from app.core.db import (
    ORG_SCOPED_TABLES,
    Base,
    OrgScopedMixin,
    TimestampMixin,
    bind_org_context,
    make_engine,
    make_session_factory,
    rls_statements,
)


class _SampleRow(Base, OrgScopedMixin, TimestampMixin):
    _tablename_ = "sample_rows"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String)


def test_org_scoped_table_registered_for_rls():
    assert "sample_rows" in ORG_SCOPED_TABLES


def test_rls_statements_shape():
    stmts = rls_statements("findings")
    assert stmts[0] == "ALTER TABLE findings ENABLE ROW LEVEL SECURITY"
    assert "current_setting('app.org_id')::uuid" in stmts[1]
    assert "CREATE POLICY org_isolation ON findings" in stmts[1]


def test_session_roundtrip_on_sqlite():
    engine = make_engine(Settings(database_url="sqlite+pysqlite:///:memory:"))
    Base.metadata.create_all(engine, tables=[_SampleRow.__table__])
    factory = make_session_factory(engine)
    org = uuid.uuid4()
    with factory() as session:
        # bind_org_context is a no-op on SQLite but must not raise (spec B1 path)
        bind_org_context(session, org)
        session.add(_SampleRow(id=uuid.uuid4(), org_id=org, label="hi"))
        session.commit()
    with factory() as session:
        rows = session.query(_SampleRow).all()
        assert len(rows) == 1
        assert rows[0].org_id == org
        assert rows[0].created_at is not None


def test_app_publishes_db_capabilities():
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(Settings(enabled_modules="health", database_url="sqlite:///:memory:"))
    caps = TestClient(app).get("/api/health").json()["capabilities"]
    assert "db.engine" in caps
    assert "db.sessionmaker" in caps
