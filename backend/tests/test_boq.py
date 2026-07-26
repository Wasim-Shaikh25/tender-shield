"""Deterministic BOQ engine tests, asserted against the synthetic sample
tender's gold answer (evals/in-works/sample_tender/)."""

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.modules.boq.engine import SpecTextIndex, normalize, run_checks, scope_gaps
from app.modules.rulepacks.loader import RulePackLoader

SAMPLE = Path(__file__).resolve().parents[2] / "evals" / "in-works" / "sample_tender"


@pytest.fixture
def boq_df() -> pd.DataFrame:
    return pd.read_csv(SAMPLE / "boq.csv")


@pytest.fixture
def pack():
    return RulePackLoader().get_pack("in-works")


def test_normalize_canonicalizes_units_and_computes_amount(boq_df, pack):
    out = normalize(boq_df, pack.unit_canon)
    # Cum and cum both fold to m3
    assert set(out.loc[out.src_row.isin([1, 2]), "unit_canon"]) == {"m3"}
    assert out.loc[out.src_row == 6, "amount_calc"].iloc[0] == 1_144_000.0  # 220*5200


def test_checks_catch_exactly_the_planted_defects(boq_df, pack):
    out = normalize(boq_df, pack.unit_canon)
    findings = run_checks(
        out,
        tolerance=pack.boq_checks.arithmetic_tolerance,
        outlier_quantile=pack.boq_checks.qty_outlier_quantile,
        outlier_multiplier=pack.boq_checks.qty_outlier_multiplier,
    )
    categories = sorted(f.category for f in findings)
    # duplicate fires on BOTH rows 1 and 2 → two duplicate findings
    assert categories == ["arith", "blank_rate", "duplicate", "duplicate", "grand_total"]
    assert all(f.source.value == "deterministic_check" for f in findings)


def test_determinism_identical_output_on_rerun(boq_df, pack):
    out = normalize(boq_df, pack.unit_canon)
    a = [f.model_dump() for f in run_checks(out)]
    b = [f.model_dump() for f in run_checks(out)]
    assert a == b


def test_scope_gaps_match_gold_and_no_false_positive(boq_df, pack):
    spec_text = (SAMPLE / "conditions.md").read_text()
    gaps = scope_gaps(boq_df, SpecTextIndex(spec_text), pack.trade_checklists["civil_structure"])
    fired = sorted(g.category for g in gaps)
    assert fired == ["anti_termite", "backfilling", "dewatering", "shoring", "soil_disposal"]
    # waterproofing is triggered by 'basement' but BOQ row 9 covers it → no gap
    assert "waterproofing" not in fired
    dewatering = next(g for g in gaps if g.category == "dewatering")
    assert dewatering.source_page == 1  # trigger appears on page 1


def test_missing_columns_raises(pack):
    with pytest.raises(ValueError):
        run_checks(normalize(pd.DataFrame({"unit_raw": ["cum"]}), pack.unit_canon))


def test_engine_degrades_without_rulepacks():
    # boq enabled, rulepacks DISABLED → engine uses fallback unit map, still runs
    app = create_app(Settings(enabled_modules="health,boq"))
    client = TestClient(app)
    body = client.get("/api/boq").json()
    assert body["engine"] == "deterministic (zero LLM)"
    assert body["available_checklists"] == []  # no pack → degraded, not crashed


def test_engine_uses_pack_when_rulepacks_enabled():
    app = create_app(Settings(enabled_modules="health,rulepacks,boq"))
    client = TestClient(app)
    body = client.get("/api/boq").json()
    assert set(body["available_checklists"]) == {"civil_structure", "electrical", "hvac"}


def test_boq_run_persists_defects_via_findings():
    import app.modules.auth.models  # noqa: F401
    import app.modules.findings.models  # noqa: F401
    import app.modules.ingestion.models  # noqa: F401
    from app.core.db import Base

    application = create_app(
        Settings(
            enabled_modules="health,rulepacks,auth,ingestion,findings,boq",
            database_url="sqlite:///:memory:",
        )
    )
    Base.metadata.create_all(application.state.ctx.registry.require("db.engine"))
    client = TestClient(application)
    client.post(
        "/api/auth/signup",
        json={"email": "bq@x.com", "password": "hunter2hunter2", "workspace_name": "Acme"},
    )
    tok = client.post(
        "/api/auth/login", json={"email": "bq@x.com", "password": "hunter2hunter2"}
    ).json()["access_token"]
    h = {"authorization": f"Bearer {tok}"}
    opp_id = client.post("/api/ingestion/opportunities", json={"title": "Depot"}, headers=h).json()[
        "id"
    ]

    csv_text = (SAMPLE / "boq.csv").read_text()
    out = client.post(f"/api/boq/opportunities/{opp_id}/run", json={"csv": csv_text}, headers=h)
    assert out.status_code == 200
    cats = {f["category"] for f in out.json()["findings"]}
    assert {"arith", "duplicate", "blank_rate", "grand_total"} <= cats

    # persisted under producer 'boq' and visible in the shared findings register
    listed = client.get(f"/api/findings/opportunities/{opp_id}", headers=h).json()["findings"]
    assert any(f["producer"] == "boq" and f["category"] == "arith" for f in listed)
