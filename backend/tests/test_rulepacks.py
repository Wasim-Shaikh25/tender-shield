from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.modules.rulepacks.loader import RulePackLoader

PHASE0_PATTERN_IDS = {
    "payment_terms_extended",
    "price_escalation_barred",
    "liquidated_damages_uncapped",
    "defect_liability_retention",
    "termination_for_convenience",
}


def test_in_works_pack_loads_with_five_unvalidated_sourced_patterns():
    loader = RulePackLoader()
    pack = loader.get_pack("in-works")
    assert pack.version_tag.startswith("in-works@")
    assert set(pack.patterns) == PHASE0_PATTERN_IDS
    assert pack.load_errors == {}
    for pattern in pack.patterns.values():
        assert pattern.confidence == "unvalidated"  # Doc §14.1: pre-QS state
        assert pattern.source.strip()


def test_unit_canon_normalizes_indian_boq_chaos():
    pack = RulePackLoader().get_pack("in-works")
    for raw in ("cum", "cu.m", "m³", "rmt", "sqm", "tonne"):
        assert raw in pack.unit_canon
    assert pack.unit_canon["cum"] == "m3"
    assert pack.unit_canon["rmt"] == "m"


def test_validated_only_hides_unvalidated_patterns():
    loader = RulePackLoader()
    assert loader.list_patterns("in-works", validated_only=True) == []
    assert len(loader.list_patterns("in-works")) == 5


def test_malformed_pattern_is_skipped_not_fatal(tmp_path: Path):
    pack_dir = tmp_path / "broken-pack"
    (pack_dir / "risk_patterns").mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        "id: broken-pack\nversion: '1'\njurisdiction: IN\neffective_from: '2026-01-01'\n"
    )
    (pack_dir / "risk_patterns" / "bad.yaml").write_text("id: no_required_fields\n")
    (pack_dir / "risk_patterns" / "good.yaml").write_text(
        """
id: ok_pattern
category: payment
title: t
confidence: unvalidated
source: some public source
severity_rule: high
anchor_queries: [x]
judgment_prompt: p
"""
    )
    pack = RulePackLoader(tmp_path).get_pack("broken-pack")
    assert list(pack.patterns) == ["ok_pattern"]
    assert "risk_patterns/bad.yaml" in pack.load_errors


def test_api_exposes_packs_and_patterns():
    app = create_app(Settings(enabled_modules="health,rulepacks"))
    client = TestClient(app)
    packs = client.get("/api/rulepacks").json()["packs"]
    assert any(p["id"] == "in-works" and p["patterns"] == 5 for p in packs)
    body = client.get("/api/rulepacks/in-works/patterns").json()
    assert {p["id"] for p in body["patterns"]} == PHASE0_PATTERN_IDS
    assert client.get("/api/rulepacks/nope/patterns").status_code == 404
    # capability is registered and visible via health
    caps = client.get("/api/health").json()["capabilities"]
    assert "rulepacks.loader" in caps
