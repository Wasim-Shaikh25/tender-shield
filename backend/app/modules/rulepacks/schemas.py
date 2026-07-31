"""Pydantic schemas for rule-pack YAML (spec rulepacks B1). Validation at load
time is the safety gate: a malformed pattern is skipped, never crashes the app."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PlaybookHint(BaseModel):
    acceptable: str
    flag_when: str


class PriceImpact(BaseModel):
    """Optional risk-to-price loading declaration on a pattern (TS-202,
    `specs/modules/pricing-intel.md`). `formula` names a versioned, pure
    function in `app.modules.pricing.formulas` — never evaluated as
    free-form code, and never itself computed by an LLM (`CLAUDE.md` §4).
    `inputs` lists the fact names the formula requires; a fact missing at
    computation time means no loading is produced, never a default.
    """

    basis: Literal["percent_of_contract_value", "per_unit", "lump_sum"]
    formula: str = Field(min_length=1)
    inputs: list[str] = Field(min_length=1)
    confidence: Literal["unvalidated", "validated"] = "unvalidated"


class RiskPattern(BaseModel):
    id: str
    category: str
    title: str
    confidence: Literal["unvalidated", "validated"]
    source: str = Field(min_length=1)  # public source citation is mandatory (Doc §14.1)
    severity_rule: str
    anchor_queries: list[str] = Field(min_length=1)
    judgment_prompt: str
    negative_examples: list[str] = Field(default_factory=list)
    default_playbook: PlaybookHint | None = None
    suggested_clarification: str | None = None
    industry_reason: str | None = None
    affected_trades: list[str] = Field(default_factory=list)
    absence_is_finding: bool = False
    price_impact: PriceImpact | None = None


class ChecklistItem(BaseModel):
    key: str
    label: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    triggers: list[str] = Field(min_length=1)
    boq_patterns: list[str] = Field(min_length=1)


class TradeChecklist(BaseModel):
    id: str
    trade: str
    confidence: Literal["unvalidated", "validated"] = "unvalidated"
    source: str = Field(min_length=1)
    items: list[ChecklistItem] = Field(min_length=1)


class DocType(BaseModel):
    label: str
    anchors: list[str] = Field(min_length=1)


class NoticeCategory(BaseModel):
    """One contractual notice regime (e.g. a claim time-bar). Universal by
    default; a regional overlay may override any field by `key` (spec
    rulepacks B7)."""

    key: str
    label: str
    typical_days: int | None = None
    # Whether a well-formed contract of this standard is expected to carry the
    # regime — drives deterministic gap detection when the contract omits it.
    expected: bool = False
    keywords: list[str] = Field(default_factory=list)
    note: str | None = None


class NoticeStandard(BaseModel):
    id: str
    scope: str = "universal"  # "universal" | a region/jurisdiction code (e.g. "IN")
    confidence: Literal["unvalidated", "validated"] = "unvalidated"
    source: str = Field(min_length=1)
    categories: list[NoticeCategory] = Field(default_factory=list)


class RateScheduleItem(BaseModel):
    """One published Schedule-of-Rates line (TS-204). `code` is the
    authority's own item code — the only thing a high-confidence match may key
    on (`specs/modules/pricing-intel.md` — code match vs description match are
    two different confidence bands, never blended)."""

    code: str = Field(min_length=1)
    description: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    rate_minor: int  # published rate in minor currency units (CLAUDE.md §4)


class RateSchedule(BaseModel):
    id: str
    authority: str = Field(min_length=1)  # e.g. "cpwd", "mh-pwd"
    year: str = Field(min_length=1)
    currency: str = Field(min_length=1)
    confidence: Literal["unvalidated", "validated"] = "unvalidated"
    source: str = Field(min_length=1)
    items: list[RateScheduleItem] = Field(default_factory=list)


class BoqCheckConfig(BaseModel):
    arithmetic_tolerance: float = 1.0
    qty_outlier_quantile: float = 0.99
    qty_outlier_multiplier: float = 3


class PackMeta(BaseModel):
    id: str
    version: str
    jurisdiction: str
    effective_from: str
    effective_to: str | None = None
    description: str = ""
    reviewer_signoff: str | None = None
    sources: list[str] = Field(default_factory=list)


class RulePack(BaseModel):
    meta: PackMeta
    patterns: dict[str, RiskPattern] = Field(default_factory=dict)
    doc_types: dict[str, DocType] = Field(default_factory=dict)
    expected_documents: list[str] = Field(default_factory=list)
    unit_canon: dict[str, str] = Field(default_factory=dict)
    boq_checks: BoqCheckConfig = Field(default_factory=BoqCheckConfig)
    trade_checklists: dict[str, TradeChecklist] = Field(default_factory=dict)
    playbooks: dict[str, dict] = Field(default_factory=dict)
    # Keyed by scope ("universal", "IN", …). Merged on demand via
    # RulePackLoader.notice_standard(region).
    notice_standards: dict[str, NoticeStandard] = Field(default_factory=dict)
    # Keyed by "<authority>/<year>" (TS-204). Ships empty in `in-works` — real
    # published Schedule-of-Rates figures are regulatory data that must be
    # entered from an authoritative source, not invented by a coding task; see
    # rulepacks/in-works/rates/README.md.
    rate_schedules: dict[str, RateSchedule] = Field(default_factory=dict)
    load_errors: dict[str, str] = Field(default_factory=dict)

    @property
    def version_tag(self) -> str:
        """Embedded into every generated artifact (Doc §2.4), e.g. in-works@2026.07.1."""
        return f"{self.meta.id}@{self.meta.version}"
