"""PricingService — binds rule-pack config and soft dependencies to the pure
`loading`/`benchmark`/`cashflow` engines, and persists results.

Every consumed capability (`findings.store_factory`, `rulepacks.loader`,
`boq.engine`, `review.service_factory`) is resolved lazily via the registry —
never imported from the sibling module directly (`CLAUDE.md` §2). Absence of
any of them degrades gracefully rather than crashing (spec core B2)."""

from __future__ import annotations

import io
import uuid
from collections.abc import Callable
from typing import Any

import pandas as pd
from sqlalchemy import delete, select

from app.modules.pricing.benchmark import benchmark
from app.modules.pricing.cashflow import CashflowInputs, run_cashflow
from app.modules.pricing.loading import compute_loadings
from app.modules.pricing.models import PiCashflowRun, PiLoading, PiRateMatch


class PricingError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class PricingService:
    PACK_ID = "in-works"

    def __init__(
        self,
        session,
        *,
        findings_factory: Callable[[Any], Any] | None = None,
        ingestion_factory: Callable[[Any], Any] | None = None,
        rulepacks_loader_provider: Callable[[], Any | None] | None = None,
        boq_engine_provider: Callable[[], Any | None] | None = None,
        review_factory: Callable[[Any], Any] | None = None,
    ):
        self.s = session
        self._findings_factory = findings_factory
        self._ingestion_factory = ingestion_factory
        self._rulepacks_loader_provider = rulepacks_loader_provider
        self._boq_engine_provider = boq_engine_provider
        self._review_factory = review_factory

    def _pack(self):
        loader = self._rulepacks_loader_provider() if self._rulepacks_loader_provider else None
        return loader.get_pack(self.PACK_ID) if loader else None

    def _opportunity(self, workspace_id, opportunity_id):
        if self._ingestion_factory is None:
            return None
        return self._ingestion_factory(self.s).get_opportunity(workspace_id, opportunity_id)

    def _require_review_gate(self, workspace_id, opportunity_id) -> None:
        """Pricing artifacts inherit the export gate (spec §Guardrails 1/2):
        no pricing output — loading or cashflow — until review is complete.
        Fails open only when the `review` module itself is disabled, matching
        every other module's soft-dependency degradation; a workspace running
        without `review` enabled has no gate to enforce in the first place."""
        if self._review_factory is None:
            return
        gate = self._review_factory(self.s).gate(workspace_id, opportunity_id)
        if not gate.get("export_allowed", False):
            raise PricingError("review_incomplete")

    # -- loadings -----------------------------------------------------------

    def get_loadings(
        self,
        workspace_id,
        opportunity_id,
        *,
        contract_value_minor: int | None = None,
        currency: str | None = None,
        facts_by_finding: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict]:
        self._require_review_gate(workspace_id, opportunity_id)
        pack = self._pack()
        patterns = pack.patterns if pack else {}
        rulepack_version = pack.version_tag if pack else "unknown"

        opp = self._opportunity(workspace_id, opportunity_id)
        if opp is None:
            raise PricingError("opportunity_not_found")
        effective_contract_value = contract_value_minor
        if effective_contract_value is None:
            if opp.contract_value_minor is None:
                raise PricingError("contract_value_required")
            effective_contract_value = opp.contract_value_minor
        effective_currency = currency or opp.currency or "INR"

        facts_override = facts_by_finding or {}
        findings = []
        row_facts: dict[str, dict] = {}
        if self._findings_factory is not None:
            rows = self._findings_factory(self.s).list(workspace_id, opportunity_id)
            findings = [
                {
                    "id": str(r.id),
                    "pattern_id": r.pattern_id,
                    "review_status": r.review_status,
                }
                for r in rows
            ]
            row_facts = {str(r.id): (r.facts or {}) for r in rows}

        merged_facts = {
            fid: {**row_facts.get(fid, {}), **facts_override.get(fid, {})}
            for fid in set(row_facts) | set(facts_override)
        }

        results = compute_loadings(
            findings,
            patterns,
            merged_facts,
            contract_value_minor=effective_contract_value,
            currency=effective_currency,
            rulepack_version=rulepack_version,
        )
        self._persist_loadings(workspace_id, opportunity_id, results)
        return [r.to_dict() for r in results]

    def _persist_loadings(self, workspace_id, opportunity_id, results) -> None:
        ws = uuid.UUID(str(workspace_id))
        opp = uuid.UUID(str(opportunity_id))
        self.s.execute(
            delete(PiLoading).where(
                PiLoading.workspace_id == ws, PiLoading.opportunity_id == opp
            )
        )
        self.s.add_all(
            PiLoading(
                workspace_id=ws,
                opportunity_id=opp,
                finding_id=uuid.UUID(r.finding_id),
                pattern_id=r.pattern_id,
                produced=r.produced,
                amount_minor=r.amount_minor,
                currency=r.currency,
                basis=r.basis,
                formula=r.formula,
                rulepack_version=r.rulepack_version,
                inputs_used=r.inputs_used,
                missing_inputs=r.missing_inputs,
                reason=r.reason,
            )
            for r in results
        )
        self.s.commit()

    # -- rate benchmark -------------------------------------------------------

    def get_rate_benchmark(
        self,
        workspace_id,
        opportunity_id,
        csv_text: str,
        *,
        authority: str | None = None,
        year: str | None = None,
    ) -> dict:
        self._require_review_gate(workspace_id, opportunity_id)
        pack = self._pack()
        boq_engine = self._boq_engine_provider() if self._boq_engine_provider else None
        if boq_engine is None:
            raise PricingError("boq_unavailable")

        df = pd.read_csv(io.StringIO(csv_text))
        normalized = boq_engine.normalize_dataframe(df)
        boq_rows = normalized.to_dict("records")

        schedule = None
        if pack and authority and year:
            schedule = pack.rate_schedules.get(f"{authority}/{year}")

        result = benchmark(boq_rows, schedule)
        self._persist_rate_matches(workspace_id, opportunity_id, result)
        return result.to_dict()

    def _persist_rate_matches(self, workspace_id, opportunity_id, result) -> None:
        ws = uuid.UUID(str(workspace_id))
        opp = uuid.UUID(str(opportunity_id))
        self.s.execute(
            delete(PiRateMatch).where(
                PiRateMatch.workspace_id == ws, PiRateMatch.opportunity_id == opp
            )
        )
        self.s.add_all(
            PiRateMatch(
                workspace_id=ws,
                opportunity_id=opp,
                src_row=m.src_row,
                boq_description=m.boq_description,
                boq_unit=m.boq_unit,
                boq_rate_minor=m.boq_rate_minor,
                matched_by=m.matched_by,
                schedule_id=result.schedule_id,
                schedule_code=m.schedule_code,
                schedule_description=m.schedule_description,
                schedule_rate_minor=m.schedule_rate_minor,
                variance_minor=m.variance_minor,
                variance_pct=m.variance_pct,
            )
            for m in result.matches
        )
        self.s.commit()

    # -- cashflow -------------------------------------------------------------

    def run_cashflow_for_opportunity(
        self, workspace_id, opportunity_id, inputs: CashflowInputs, *, currency: str = "INR"
    ) -> dict:
        self._require_review_gate(workspace_id, opportunity_id)
        result = run_cashflow(inputs, currency=currency)
        self._persist_cashflow(workspace_id, opportunity_id, inputs, result)
        return result.to_dict()

    def _persist_cashflow(self, workspace_id, opportunity_id, inputs, result) -> None:
        row = PiCashflowRun(
            workspace_id=uuid.UUID(str(workspace_id)),
            opportunity_id=uuid.UUID(str(opportunity_id)),
            inputs={
                "contract_value_minor": inputs.contract_value_minor,
                "duration_months": inputs.duration_months,
                "cost_of_capital_pa": inputs.cost_of_capital_pa,
                "payment_days": inputs.payment_days,
                "retention_pct": inputs.retention_pct,
                "retention_release_month": inputs.retention_release_month,
                "mobilization_advance_pct": inputs.mobilization_advance_pct,
                "mobilization_recovery_months": inputs.mobilization_recovery_months,
            },
            assumptions=result.assumptions,
            monthly=[m.to_dict() for m in result.monthly],
            peak_requirement_minor=result.peak_requirement_minor,
            peak_month=result.peak_month,
            total_financing_cost_minor=result.total_financing_cost_minor,
            currency=result.currency,
        )
        self.s.add(row)
        self.s.commit()

    def list_loadings(self, workspace_id, opportunity_id) -> list[PiLoading]:
        return list(
            self.s.scalars(
                select(PiLoading).where(
                    PiLoading.workspace_id == uuid.UUID(str(workspace_id)),
                    PiLoading.opportunity_id == uuid.UUID(str(opportunity_id)),
                )
            )
        )
