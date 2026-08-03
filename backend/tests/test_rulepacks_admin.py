"""Rulepack admin (TS-348): upload, versioning, activation, per-opportunity multi-pack selection."""

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from tests.helpers import auth_headers

MODULES = (
    "health,rulepacks,auth,ingestion,findings,risk,review,boq,baseline,"
    "change,evidence,claims,outcomes,controltower,express,export,drawings"
)


def _zip_pack(pack_dir: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in pack_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(pack_dir.parent).as_posix())
    return buf.getvalue()


@pytest.fixture
def client(tmp_path):
    application = create_app(
        Settings(
            enabled_modules=MODULES,
            database_url="sqlite:///:memory:",
            storage_type="local",
            storage_dir=str(tmp_path / "storage"),
            rulepacks_dir=str(Path(__file__).resolve().parents[2] / "rulepacks"),
        )
    )
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    return TestClient(application)


def _workspace_headers(client, email="rp-admin@example.com"):
    h = auth_headers(client, email)
    return h


def test_upload_list_and_activate(client):
    h = _workspace_headers(client)
    pack_dir = Path(__file__).resolve().parents[2] / "rulepacks" / "in-works"
    archive = _zip_pack(pack_dir)

    r = client.post(
        "/api/rulepacks/admin/packs",
        data={"scope": "workspace"},
        files={"archive": ("in-works.zip", io.BytesIO(archive), "application/zip")},
        headers=h,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["pack_id"] == "in-works"
    assert data["scope"] == "workspace"
    assert data["status"] == "draft"
    rid = data["id"]

    r = client.get("/api/rulepacks/admin/packs", headers=h)
    assert r.status_code == 200, r.text
    assert any(p["id"] == rid for p in r.json()["packs"])

    r = client.post(f"/api/rulepacks/admin/packs/{rid}/activate", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["is_active"]
    assert r.json()["status"] == "active"

    r = client.delete(f"/api/rulepacks/admin/packs/{rid}", headers=h)
    assert r.status_code == 200, r.text


def test_version_bump_on_duplicate_upload(client):
    h = _workspace_headers(client, "rp-version@example.com")
    pack_dir = Path(__file__).resolve().parents[2] / "rulepacks" / "in-works"
    archive = _zip_pack(pack_dir)

    def upload():
        return client.post(
            "/api/rulepacks/admin/packs",
            data={"scope": "workspace"},
            files={"archive": ("in-works.zip", io.BytesIO(archive), "application/zip")},
            headers=h,
        )

    r1 = upload()
    r2 = upload()
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert r1.json()["version"] != r2.json()["version"]


def test_apply_and_query_opportunity_packs(client):
    h = _workspace_headers(client, "rp-apply@example.com")
    pack_dir = Path(__file__).resolve().parents[2] / "rulepacks" / "in-works"
    archive = _zip_pack(pack_dir)

    r = client.post(
        "/api/rulepacks/admin/packs",
        data={"scope": "workspace"},
        files={"archive": ("in-works.zip", io.BytesIO(archive), "application/zip")},
        headers=h,
    )
    assert r.status_code == 200, r.text
    rid = r.json()["id"]

    r = client.post(
        "/api/ingestion/opportunities", json={"title": "Rulepack test"}, headers=h
    )
    assert r.status_code == 200, r.text
    opp_id = r.json()["id"]

    r = client.post(
        f"/api/rulepacks/opportunities/{opp_id}/packs",
        json={"pack_ids": [rid]},
        headers=h,
    )
    assert r.status_code == 200, r.text
    applied = r.json()["packs"]
    assert len(applied) == 1
    assert applied[0]["id"] == rid

    r = client.get(f"/api/rulepacks/opportunities/{opp_id}/packs", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["packs"][0]["id"] == rid


def test_private_workspace_packs_are_isolated(client):
    h1 = _workspace_headers(client, "rp-ws1@example.com")
    h2 = _workspace_headers(client, "rp-ws2@example.com")
    pack_dir = Path(__file__).resolve().parents[2] / "rulepacks" / "in-works"
    archive = _zip_pack(pack_dir)

    r = client.post(
        "/api/rulepacks/admin/packs",
        data={"scope": "workspace"},
        files={"archive": ("in-works.zip", io.BytesIO(archive), "application/zip")},
        headers=h1,
    )
    rid = r.json()["id"]

    r = client.get("/api/rulepacks/admin/packs", headers=h2)
    assert rid not in {p["id"] for p in r.json()["packs"]}
