"""marketdata module tests (TS-195/196/198/199)."""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

import app.modules.marketdata.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base, make_engine, make_session_factory
from app.main import create_app
from app.modules.marketdata.aggregates import MIN_SAMPLE_SIZE, compute_aggregates
from app.modules.marketdata.models import MdAward, MdEmployer, MdTender
from app.modules.marketdata.resolution import resolve_buyer
from app.modules.marketdata.store import MarketDataStore
from app.modules.rulepacks.loader import RulePackLoader


def test_marketdata_boots_and_returns_insufficient_data():
    app = create_app(
        Settings(
            enabled_modules="health,auth,marketdata",
            database_url="sqlite:///:memory:",
        )
    )
    client = TestClient(app)
    body = client.get("/api/marketdata").json()
    assert body["status"] == "ready"


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


@pytest.fixture
def families():
    data = RulePackLoader().employer_families("in-works")
    return data.model_dump() if data is not None else None


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


def test_resolve_cpwd_buyer_from_alias(families):
    result = resolve_buyer("E.E., PWD Div-II, Pune", families)
    assert result.family == "CPWD"
    assert result.confidence in {"exact_alias", "pattern"}
    assert result.division == "ii"


def test_unresolved_buyer_stays_unresolved(families):
    result = resolve_buyer("Totally Unknown Authority Ltd", families)
    assert result.family is None
    assert result.confidence == "unresolved"


def _seed_cpwd_awards(session, families, count: int) -> MarketDataStore:
    store = MarketDataStore(session)
    for i in range(count):
        tender = store.upsert_tender(
            ocid=f"ocds-cpwd-{i}",
            buyer_name="central public works department",
            source_id=f"T-{i}",
            source_url=f"https://example.com/t/{i}",
            classification="works",
            value_minor=10_000_000,
            tender_end="2024-01-01",
            adapter_name="test",
            adapter_version="0.1.0",
        )
        store.resolve_tender_buyer(tender, families)
        store.upsert_award(
            ocid=tender.ocid,
            tender_id=tender.id,
            winner=f"Winner {i % 3}",
            value_minor=9_500_000 + i * 1000,
            currency="INR",
            bidder_count=3 + (i % 5),
            award_date="2025-08-01",
            source_url=f"https://example.com/a/{i}",
        )
    store.refresh_profile("CPWD")
    return store


def test_profile_suppressed_below_minimum(session, families):
    store = _seed_cpwd_awards(session, families, MIN_SAMPLE_SIZE - 1)
    profile = store.profile_by_family("CPWD")
    payload = MarketDataStore.suppression_payload("CPWD", profile)
    assert payload["status"] == "insufficient_data"
    assert payload["n"] == MIN_SAMPLE_SIZE - 1


def test_profile_returns_aggregates_at_minimum(session, families):
    store = _seed_cpwd_awards(session, families, MIN_SAMPLE_SIZE)
    profile = store.profile_by_family("CPWD")
    payload = MarketDataStore.suppression_payload("CPWD", profile)
    assert payload["status"] == "ok"
    assert payload["n"] == MIN_SAMPLE_SIZE
    assert payload["aggregates"]["bidder_count_p50"] is not None


def test_aggregates_are_deterministic(session, families):
    store = _seed_cpwd_awards(session, families, MIN_SAMPLE_SIZE)
    first = store.profile_by_family("CPWD").aggregates
    second = store.refresh_profile("CPWD").aggregates
    assert first == second


def test_comparable_awards_discloses_filter(session, families):
    _seed_cpwd_awards(session, families, MIN_SAMPLE_SIZE + 1)
    from app.modules.marketdata.service import MarketDataService

    svc = MarketDataService(session, loader=RulePackLoader())
    body = svc.comparable_awards("00000000-0000-0000-0000-000000000001", employer_family="CPWD")
    assert body["status"] == "ok"
    assert body["filter"]["employer_family"] == "CPWD"
    assert body["n"] >= MIN_SAMPLE_SIZE


def test_compute_aggregates_handles_empty_records():
    assert compute_aggregates([])["bidder_count_p50"] is None
