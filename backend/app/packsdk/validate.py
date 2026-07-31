"""Pack schema + lint validation (TS-220).

Reuses `RulePackLoader` for schema conformance — the Pydantic models in
`app.modules.rulepacks.schemas` **are** the schema, so there is exactly one
definition of a valid pack, not one for the product and a looser one for
third parties. This module adds lint rules the loader itself does not
enforce because production optimizes for graceful degradation (skip a bad
file, keep booting) where pre-publish validation should instead fail loudly.
"""

from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.modules.rulepacks.loader import RulePackLoader


@dataclass
class LintIssue:
    severity: str  # "error" | "warning"
    code: str
    message: str


@dataclass
class ValidationReport:
    pack_id: str
    schema_errors: dict[str, str] = field(default_factory=dict)  # from RulePackLoader.load_errors
    issues: list[LintIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[LintIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[LintIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.schema_errors and not self.errors

    def to_dict(self) -> dict:
        return {
            "pack_id": self.pack_id,
            "ok": self.ok,
            "schema_errors": self.schema_errors,
            "errors": [{"code": i.code, "message": i.message} for i in self.errors],
            "warnings": [{"code": i.code, "message": i.message} for i in self.warnings],
        }


def _valid_severity_rule(rule: str) -> bool:
    try:
        ast.parse(rule, mode="eval")
    except SyntaxError:
        return False
    return True


def validate_pack(pack_dir: str | Path, pack_id: str | None = None) -> ValidationReport:
    """`pack_dir` is the directory containing `pack.yaml` (i.e. a pack root,
    not the `rulepacks/` folder above it). `pack_id` defaults to the
    directory name, matching `pack.yaml`'s own `id` field convention."""
    pack_dir = Path(pack_dir)
    pack_id = pack_id or pack_dir.name
    loader = RulePackLoader(root=pack_dir.parent)
    pack = loader.get_pack(pack_dir.name, reload=True)
    report = ValidationReport(pack_id=pack_id, schema_errors=dict(pack.load_errors))

    if pack.meta.id != pack_dir.name:
        report.issues.append(
            LintIssue(
                "warning",
                "id_mismatch",
                f"pack.yaml id {pack.meta.id!r} does not match directory name {pack_dir.name!r}",
            )
        )

    if not pack.patterns:
        report.issues.append(
            LintIssue("warning", "no_patterns", "pack defines zero risk patterns")
        )

    for pattern_id, pattern in pack.patterns.items():
        if not pattern.source.strip():
            report.issues.append(
                LintIssue(
                    "error", "missing_source", f"pattern {pattern_id!r} has an empty source"
                )
            )
        if not _valid_severity_rule(pattern.severity_rule):
            report.issues.append(
                LintIssue(
                    "error",
                    "bad_severity_rule",
                    f"pattern {pattern_id!r} severity_rule is not valid Python expression syntax: "
                    f"{pattern.severity_rule!r}",
                )
            )
        if pattern.price_impact is not None:
            try:
                from app.modules.pricing.formulas import get_formula

                if get_formula(pattern.price_impact.formula) is None:
                    report.issues.append(
                        LintIssue(
                            "warning",
                            "unregistered_formula",
                            f"pattern {pattern_id!r} references price_impact formula "
                            f"{pattern.price_impact.formula!r}, which is not registered in "
                            "app.modules.pricing.formulas — it will produce no loading "
                            "until either the formula ships or the pack drops the reference",
                        )
                    )
            except ImportError:
                pass  # pricing module not installed in this environment; not this validator's job

    # Duplicate ids across YAML files silently overwrite in RulePackLoader
    # (spec core B6's cache is a dict keyed by id) — a duplicate is exactly
    # the kind of authoring mistake pre-publish validation exists to catch.
    _check_duplicate_ids(pack_dir / "risk_patterns", "pattern", report)
    _check_duplicate_ids(pack_dir / "boq" / "trade_checklists", "checklist", report)

    for checklist_id, checklist in pack.trade_checklists.items():
        keys = [i.key for i in checklist.items]
        dupes = [k for k, n in Counter(keys).items() if n > 1]
        if dupes:
            report.issues.append(
                LintIssue(
                    "error",
                    "duplicate_item_key",
                    f"checklist {checklist_id!r} has duplicate item keys: {dupes}",
                )
            )

    return report


def _check_duplicate_ids(directory: Path, label: str, report: ValidationReport) -> None:
    if not directory.is_dir():
        return
    ids_by_id: dict[str, list[str]] = {}
    for path in sorted(directory.glob("*.yaml")):
        with path.open() as fh:
            raw = yaml.safe_load(fh) or {}
        obj_id = raw.get("id")
        if obj_id:
            ids_by_id.setdefault(obj_id, []).append(path.name)
    for obj_id, files in ids_by_id.items():
        if len(files) > 1:
            report.issues.append(
                LintIssue(
                    "error",
                    "duplicate_id",
                    f"{label} id {obj_id!r} declared in multiple files: {files} "
                    "— only the last one loaded survives",
                )
            )
