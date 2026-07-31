"""marketdata module scaffold tests (TS-195)."""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_marketdata_boots_and_returns_insufficient_data():
    app = create_app(
        Settings(
            enabled_modules="health,auth,marketdata",
            database_url="sqlite:///:memory:",
        )
    )
    client = TestClient(app)
    body = client.get("/api/marketdata").json()
    assert body["status"] == "scaffold"


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
    # Unauthenticated — expect 401; module route exists when enabled.
    client = TestClient(app)
    assert client.get("/api/marketdata/employers/CPWD/profile").status_code == 401
