from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

import app.modules.auth.models  # noqa: F401
from app.core.config import Settings
from app.core.db import Base
from app.main import create_app
from app.modules.auth import security as sec
from app.modules.rulepacks.loader import RulePackLoader

PHASE0_PATTERN_IDS = {
    "payment_terms_extended",
    "price_escalation_barred",
    "liquidated_damages_uncapped",
    "defect_liability_retention",
    "termination_for_convenience",
}

SAE_PATTERN_IDS = {
    "sae_customs_gst_variation",
    "sae_split_delivery_erection_ld",
    "sae_performance_guarantee_tests",
    "sae_free_issue_material",
    "sae_om_tail_obligations",
}

ALL_IN_WORKS_PATTERN_IDS = PHASE0_PATTERN_IDS | SAE_PATTERN_IDS


def test_in_works_pack_loads_with_five_unvalidated_sourced_patterns():
    loader = RulePackLoader()
    pack = loader.get_pack("in-works")
    assert pack.version_tag.startswith("in-works@")
    assert PHASE0_PATTERN_IDS <= set(pack.patterns)
    assert pack.load_errors == {}
    for pattern in pack.patterns.values():
        assert pattern.confidence == "unvalidated"  # Doc §14.1: pre-QS state
        assert pattern.source.strip()


def test_sae_rung2_patterns_load_yaml_only():
    """Domain-ladder Rung 2 (Strategy §D.2, TS-222) — five SAE patterns, zero code."""
    pack = RulePackLoader().get_pack("in-works", reload=True)
    assert SAE_PATTERN_IDS <= set(pack.patterns)
    for pid in SAE_PATTERN_IDS:
        pattern = pack.patterns[pid]
        assert pattern.confidence == "unvalidated"
        assert pattern.source.strip()
        assert pattern.affected_trades


def test_unit_canon_normalizes_indian_boq_chaos():
    pack = RulePackLoader().get_pack("in-works")
    for raw in ("cum", "cu.m", "m³", "rmt", "sqm", "tonne"):
        assert raw in pack.unit_canon
    assert pack.unit_canon["cum"] == "m3"
    assert pack.unit_canon["rmt"] == "m"


def test_validated_only_hides_unvalidated_patterns():
    loader = RulePackLoader()
    assert loader.list_patterns("in-works", validated_only=True) == []
    assert len(loader.list_patterns("in-works")) == len(ALL_IN_WORKS_PATTERN_IDS)


def test_notice_standard_universal_base_and_india_overlay():
    loader = RulePackLoader()
    # Universal base standard on its own.
    base = loader.notice_standard("in-works")
    keys = {c.key: c for c in base.categories}
    assert keys["claim"].typical_days == 28  # FIDIC-norm universal default
    assert "escalation" not in keys  # India-specific, not in the base

    # India overlay merged ON TOP: claim tightened, escalation added, others kept.
    india = loader.notice_standard("in-works", "IN")
    ik = {c.key: c for c in india.categories}
    assert ik["claim"].typical_days == 15  # overridden by the India overlay
    assert "escalation" in ik  # region-only category appended
    assert ik["escalation"].expected is True
    assert ik["defect"].typical_days == 14  # untouched base category survives
    assert india.scope == "IN"


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
    app = create_app(
        Settings(enabled_modules="health,auth,rulepacks", database_url="sqlite:///:memory:")
    )
    engine = app.state.ctx.registry.require("db.engine")
    Base.metadata.create_all(engine)
    keys = app.state.ctx.registry.require("auth.keys")
    token = sec.mint_access(
        keys,
        user_id="00000000-0000-0000-0000-000000000001",
        workspace_id="00000000-0000-0000-0000-0000000000aa",
        role="viewer",
        email_verified=True,
        ttl=timedelta(minutes=5),
    )
    headers = {"authorization": f"Bearer {token}"}
    super_token = sec.mint_access(
        keys,
        user_id="00000000-0000-0000-0000-000000000001",
        workspace_id="00000000-0000-0000-0000-0000000000aa",
        role="viewer",
        is_superadmin=True,
        email_verified=True,
        ttl=timedelta(minutes=5),
    )
    super_headers = {"authorization": f"Bearer {super_token}"}
    client = TestClient(app)
    packs = client.get("/api/rulepacks", headers=headers).json()["packs"]
    in_works = next(p for p in packs if p["id"] == "in-works")
    assert in_works["patterns"] == len(ALL_IN_WORKS_PATTERN_IDS)
    body = client.get("/api/rulepacks/in-works/patterns", headers=headers).json()
    assert {p["id"] for p in body["patterns"]} == ALL_IN_WORKS_PATTERN_IDS
    assert client.get("/api/rulepacks/nope/patterns", headers=headers).status_code == 404
    # capability is registered and visible via health details
    caps = client.get("/api/health/details", headers=super_headers).json()["capabilities"]
    assert "rulepacks.loader" in caps


def test_document_precedence_loads_default_order_for_in_works():
    loader = RulePackLoader()
    assert loader.document_precedence("in-works") == ["addendum", "scc", "gcc", "nit"]
    # No employer_family override ships in-works today (real overrides are
    # employer-specific data, not something to invent — TS-217).
    assert loader.document_precedence("in-works", "acme-corp") == ["addendum", "scc", "gcc", "nit"]


def test_document_precedence_employer_family_override(tmp_path: Path):
    pack_dir = tmp_path / "override-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "id: override-pack\nversion: '1'\njurisdiction: IN\neffective_from: '2026-01-01'\n"
    )
    (pack_dir / "document_precedence.yaml").write_text(
        """
id: document_precedence
confidence: unvalidated
source: test fixture
default_order: [addendum, scc, gcc, nit]
employer_family_overrides:
  acme-corp: [gcc, addendum, scc, nit]
"""
    )
    loader = RulePackLoader(tmp_path)
    default_order = ["addendum", "scc", "gcc", "nit"]
    assert loader.document_precedence("override-pack") == default_order
    assert loader.document_precedence("override-pack", "acme-corp") == [
        "gcc",
        "addendum",
        "scc",
        "nit",
    ]
    assert loader.document_precedence("override-pack", "other-employer") == default_order


def test_document_precedence_absent_pack_degrades_to_empty_list(tmp_path: Path):
    pack_dir = tmp_path / "no-precedence-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "id: no-precedence-pack\nversion: '1'\njurisdiction: IN\neffective_from: '2026-01-01'\n"
    )
    loader = RulePackLoader(tmp_path)
    assert loader.document_precedence("no-precedence-pack") == []


def test_malformed_document_precedence_is_skipped_not_fatal(tmp_path: Path):
    pack_dir = tmp_path / "broken-precedence-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        "id: broken-precedence-pack\nversion: '1'\njurisdiction: IN\neffective_from: '2026-01-01'\n"
    )
    (pack_dir / "document_precedence.yaml").write_text("default_order: []\n")
    pack = RulePackLoader(tmp_path).get_pack("broken-precedence-pack")
    assert pack.document_precedence is None
    assert "document_precedence.yaml" in pack.load_errors


def test_trade_checklists_load_with_dewatering_gap_knowledge():
    pack = RulePackLoader().get_pack("in-works", reload=True)
    # Domain-ladder Rung 1 (Strategy §D.2, TS-221): civil/electrical/hvac plus
    # plumbing, fire_fighting, structural_steel, lifts — one YAML each, zero code.
    assert set(pack.trade_checklists) == {
        "civil_structure",
        "electrical",
        "hvac",
        "plumbing",
        "fire_fighting",
        "structural_steel",
        "lifts",
    }
    civil = pack.trade_checklists["civil_structure"]
    assert civil.confidence == "unvalidated"
    dewatering = next(i for i in civil.items if i.key == "dewatering")
    assert "basement" in dewatering.triggers
    assert dewatering.severity == "high"
    for checklist in pack.trade_checklists.values():
        assert checklist.source.strip()
        for item in checklist.items:
            assert item.triggers and item.boq_patterns
