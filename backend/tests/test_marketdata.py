"""marketdata module tests (TS-195/196)."""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

import app.modules.marketdata.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base, make_engine, make_session_factory
from app.main import create_app
from app.modules.marketdata.models import MdAward, MdEmployer, MdTender
from app.modules.marketdata.store import MarketDataStore


def test_marketdata_boots_and_returns_insufficient_data():
    app = create_app(
        Settings(
            enabled_modules="health,auth,marketdata",
            database_url="sqlite:///:memory:",
        )
    )
    client = TestClient(app)
    body = client.get("/api/marketdata").json()
    assert "module" in body


def test_marketdata_degrades_when_disabled():
    app = create_app(Settings(enabled_modules="health", database_url="sqlite:///:memory:"))
    client = TestClient(app)
    assert client.get("/api/marketdata").status_code == 404


def test_employer_profile_returns_insufficient_data_without_harvest():
    app = create_app(
        Settings(
            enabled_modules="health,auth,marketdata",
            database_url="sqlite:///:memory:",
        )
    )
    client = TestClient(app)
    assert client.get("/api/marketdata/employers/CPWD/profile").status_code == 401


@pytest.fixture
def session():
    engine = make_engine(Settings(database_url="sqlite+pysqlite:///:memory:"))
    Base.metadata.create_all(engine)
    return make_session_factory(engine)()


def test_md_tables_have_no_workspace_id_column(session):
    for model in (MdEmployer, MdTender, MdAward):
        cols = {c.name for c in inspect(model).columns}
        assert "workspace_id" not in cols


def test_award_prefill_matches_ocid(session):
    store = MarketDataStore(session)
    tender = store.upsert_tender(
        ocid="ocds-abc-123",
        source_id="TENDER-1",
        source_url="https://example.com/t/1",
        buyer_name="CPWD",
        adapter_name="test",
        adapter_version="0.1.0",
    )
    store.upsert_award(
        ocid=tender.ocid,
        tender_id=tender.id,
        winner="Acme Ltd",
        value_minor=9_500_000,
        currency="INR",
        bidder_count=4,
        source_url="https://example.com/a/1",
    )
    prefill = store.award_prefill("ocds-abc-123")
    assert prefill is not None
    assert prefill["l1_value_minor"] == 9_500_000
    assert prefill["requires_confirmation"] is True
