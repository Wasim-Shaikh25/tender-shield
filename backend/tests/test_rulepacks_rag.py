"""RAG-assisted rulepack expansion (TS-351)."""

import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import Base
from app.core.storage import get_storage
from app.main import create_app
from app.modules.rulepacks.rag_service import RagSuggestionService
from tests.helpers import auth_headers

MODULES = (
    "health,rulepacks,auth,ingestion,findings,risk,review,boq,baseline,"
    "change,evidence,claims,outcomes,controltower,express,export,drawings"
)


def _zip_pack_with_circular(pack_dir: Path, circular_text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in pack_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(pack_dir.parent).as_posix())
        zf.writestr("in-works/circulars/gst_circular.txt", circular_text)
    return buf.getvalue()


def _fake_llm_client(response_text: str):
    class FakeChoices:
        message = SimpleNamespace(content=response_text)

    class FakeCompletion:
        choices = [FakeChoices()]

    class FakeCompletions:
        def create(self, *args, **kwargs):
            return FakeCompletion()

    return SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))


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


def _workspace_headers(client, email="rp-rag@example.com"):
    return auth_headers(client, email)


def _upload_pack(client, h, tmp_path, circular_text=""):
    pack_dir = Path(__file__).resolve().parents[2] / "rulepacks" / "in-works"
    archive = _zip_pack_with_circular(pack_dir, circular_text)
    r = client.post(
        "/api/rulepacks/admin/packs",
        data={"scope": "workspace"},
        files={"archive": ("in-works.zip", io.BytesIO(archive), "application/zip")},
        headers=h,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _override_rag_factory(client, response_text):
    reg = client.app.state.ctx.registry
    settings = client.app.state.ctx.settings
    storage = get_storage(settings)

    def rag_factory(session):
        return RagSuggestionService(
            session,
            settings=settings,
            storage=storage,
            ingestion_factory=reg.get("ingestion.service_factory"),
            llm_client=_fake_llm_client(response_text),
        )

    reg.provide("rulepacks.rag_factory", rag_factory, replace=True)


def test_rag_suggestion_approve_creates_draft_version(client, tmp_path):
    h = _workspace_headers(client)
    circular_text = (
        "The contractor shall bear all GST variations and customs duty changes. "
        "Any increase in statutory levies after the bid due date shall be borne by the contractor."
    )
    pack = _upload_pack(client, h, tmp_path, circular_text)
    rid = pack["id"]

    # Find the source file id.
    r = client.get(f"/api/rulepacks/admin/packs/{rid}/files", headers=h)
    assert r.status_code == 200, r.text
    file_id = next(f["id"] for f in r.json()["files"] if "circular" in f["path"])

    suggestion = {
        "kind": "patterns",
        "proposed_yaml": {
            "rag_gst_variation": {
                "id": "rag_gst_variation",
                "category": "tax",
                "title": "GST and customs duty variation",
                "confidence": "unvalidated",
                "source": " gst_circular.txt",
                "severity_rule": "high",
                "anchor_queries": ["GST variations", "customs duty changes"],
                "judgment_prompt": "Check if contractor bears statutory levy variations.",
                "negative_examples": [],
            }
        },
        "rationale": "Circular explicitly shifts statutory levy risk to contractor.",
        "source_quote": "The contractor shall bear all GST variations",
        "source_page": 1,
        "confidence": "unvalidated",
    }
    _override_rag_factory(client, json.dumps([suggestion]))

    r = client.post(
        f"/api/rulepacks/admin/packs/{rid}/files/{file_id}/suggest",
        headers=h,
    )
    assert r.status_code == 200, r.text
    suggestions = r.json()["suggestions"]
    assert len(suggestions) == 1
    assert suggestions[0]["kind"] == "patterns"
    sid = suggestions[0]["id"]

    r = client.get(f"/api/rulepacks/admin/packs/{rid}/suggestions", headers=h)
    assert r.status_code == 200, r.text
    assert any(s["id"] == sid for s in r.json()["suggestions"])

    r = client.post(f"/api/rulepacks/admin/suggestions/{sid}/approve", headers=h)
    assert r.status_code == 200, r.text
    new_pack_id = r.json()["new_rulepack"]["id"]

    r = client.get("/api/rulepacks/admin/packs", headers=h)
    assert r.status_code == 200, r.text
    new_pack = next((p for p in r.json()["packs"] if p["id"] == new_pack_id), None)
    assert new_pack is not None
    assert new_pack["status"] == "draft"
    assert not new_pack["is_active"]
    assert new_pack["version"] != pack["version"]


def test_rag_suggestion_reject(client, tmp_path):
    h = _workspace_headers(client, "rp-rag-reject@example.com")
    pack = _upload_pack(client, h, tmp_path, "No relevant clause.")
    rid = pack["id"]

    r = client.get(f"/api/rulepacks/admin/packs/{rid}/files", headers=h)
    file_id = next(f["id"] for f in r.json()["files"])

    suggestion = {
        "kind": "patterns",
        "proposed_yaml": {"rag_unused": {"id": "rag_unused", "category": "test"}},
        "rationale": "Test",
        "source_quote": "No relevant",
        "source_page": 1,
        "confidence": "unvalidated",
    }
    _override_rag_factory(client, json.dumps([suggestion]))

    r = client.post(
        f"/api/rulepacks/admin/packs/{rid}/files/{file_id}/suggest",
        headers=h,
    )
    assert r.status_code == 200, r.text
    sid = r.json()["suggestions"][0]["id"]

    r = client.post(f"/api/rulepacks/admin/suggestions/{sid}/reject", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected"

    r = client.get(
        f"/api/rulepacks/admin/packs/{rid}/suggestions", params={"status": "rejected"}, headers=h
    )
    assert r.json()["suggestions"][0]["id"] == sid
