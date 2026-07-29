from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.loader import discover_module_names, load_modules
from app.main import create_app


def test_discovery_finds_health_and_skips_underscore_fixtures():
    names = discover_module_names()
    assert "health" in names
    assert all(not n.startswith("_") for n in names)


def test_broken_module_is_isolated():
    report = load_modules(["_broken", "health"])
    assert [s.name for s in report.loaded] == ["health"]
    assert "_broken" in report.failed
    assert "RuntimeError" in report.failed["_broken"]


def test_app_boots_with_explicit_module_subset():
    app = create_app(Settings(enabled_modules="health"))
    client = TestClient(app)
    body = client.get("/api/health/details").json()
    assert body["status"] == "ok"
    assert [m["name"] for m in body["modules"]] == ["health"]


def test_app_boots_with_broken_module_enabled():
    app = create_app(Settings(enabled_modules="_broken,health"))
    client = TestClient(app)
    body = client.get("/api/health/details").json()
    assert body["status"] == "ok"
    assert "_broken" in body["failed_modules"]


def test_missing_soft_dep_is_reported_not_fatal():
    report = load_modules(["health"])
    # health has no soft deps today; the report structure is the contract
    assert report.missing_soft_deps == {}
