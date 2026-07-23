"""BOQ engine facade — binds rule-pack config to the pure engine functions.

Consumes `rulepacks.loader` via the registry as a SOFT dependency, resolved
LAZILY at call time (not captured at setup) so module setup order never
matters. If the rulepacks module is disabled the loader is None and the engine
runs with built-in defaults (spec core B2 — graceful degradation).
"""

from __future__ import annotations

import io
from collections.abc import Callable

import pandas as pd

from app.core.contracts.findings import Finding
from app.modules.boq.engine import (
    SpecTextIndex,
    normalize,
    run_checks,
    scope_gaps,
)

_FALLBACK_UNIT_CANON = {"cum": "m3", "m³": "m3", "sqm": "m2", "rmt": "m", "mt": "t"}


class BoqEngine:
    def __init__(self, loader_provider: Callable[[], object | None], pack_id: str = "in-works"):
        self._loader_provider = loader_provider
        self._pack_id = pack_id

    def _pack(self):
        loader = self._loader_provider()
        return loader.get_pack(self._pack_id) if loader else None

    def check_dataframe(self, df: pd.DataFrame) -> list[Finding]:
        pack = self._pack()
        unit_canon = pack.unit_canon if pack else _FALLBACK_UNIT_CANON
        cfg = pack.boq_checks if pack else None
        normalized = normalize(df, unit_canon)
        return run_checks(
            normalized,
            tolerance=cfg.arithmetic_tolerance if cfg else 1.0,
            outlier_quantile=cfg.qty_outlier_quantile if cfg else 0.99,
            outlier_multiplier=cfg.qty_outlier_multiplier if cfg else 3,
        )

    def scope_gaps(self, df: pd.DataFrame, spec_text: str, checklist_id: str) -> list[Finding]:
        pack = self._pack()
        if not pack or checklist_id not in pack.trade_checklists:
            return []  # degrade: no checklist available
        return scope_gaps(df, SpecTextIndex(spec_text), pack.trade_checklists[checklist_id])

    def available_checklists(self) -> list[str]:
        pack = self._pack()
        return sorted(pack.trade_checklists) if pack else []


class BoqRunner:
    """Runs the deterministic BOQ engine over an uploaded workbook and persists
    the defects + scope gaps via the findings store (producer='boq'). Consumes
    ingestion (for the spec text that drives scope-gap triggers) and findings
    purely via registry capabilities."""

    PRODUCER = "boq"

    def __init__(self, session, *, engine: BoqEngine, store_factory=None, ingestion_factory=None):
        self.s = session
        self._engine = engine
        self._store_factory = store_factory
        self._ingestion_factory = ingestion_factory

    def _spec_text(self, org_id, opportunity_id) -> str:
        if not self._ingestion_factory:
            return ""
        clauses = self._ingestion_factory(self.s).list_clauses(org_id, opportunity_id)
        return "\n".join(c.text for c in clauses)

    def run_csv(self, org_id, opportunity_id, csv_text: str) -> list[Finding]:
        df = pd.read_csv(io.StringIO(csv_text))
        findings = self._engine.check_dataframe(df)
        spec_text = self._spec_text(org_id, opportunity_id)
        for checklist_id in self._engine.available_checklists():
            findings.extend(self._engine.scope_gaps(df, spec_text, checklist_id))
        if self._store_factory is not None:
            self._store_factory(self.s).replace_for_producer(
                org_id, opportunity_id, self.PRODUCER, findings
            )
        return findings
