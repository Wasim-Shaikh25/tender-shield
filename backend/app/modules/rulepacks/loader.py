"""Filesystem rule-pack loader (spec rulepacks B6)."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.modules.rulepacks.schemas import (
    DocType,
    PackMeta,
    RiskPattern,
    RulePack,
    TradeChecklist,
)

logger = logging.getLogger(__name__)

# repo-root/rulepacks — backend/ lives one level under the repo root.
DEFAULT_RULEPACKS_DIR = Path(__file__).resolve().parents[4] / "rulepacks"


def _read_yaml(path: Path) -> dict:
    # Everything except pack.yaml is optional in a pack; absent file = empty.
    if not path.is_file():
        return {}
    with path.open() as fh:
        return yaml.safe_load(fh) or {}


def _glob_yaml(directory: Path):
    return sorted(directory.glob("*.yaml")) if directory.is_dir() else []


class RulePackLoader:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root else DEFAULT_RULEPACKS_DIR
        self._cache: dict[str, RulePack] = {}

    def list_packs(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.parent.name for p in self.root.glob("*/pack.yaml"))

    def get_pack(self, pack_id: str, *, reload: bool = False) -> RulePack:
        if not reload and pack_id in self._cache:
            return self._cache[pack_id]
        pack_dir = self.root / pack_id
        meta = PackMeta.model_validate(_read_yaml(pack_dir / "pack.yaml"))
        pack = RulePack(meta=meta)

        doc_types_raw = _read_yaml(pack_dir / "doc_types.yaml")
        pack.expected_documents = doc_types_raw.get("expected_documents", [])
        for name, spec in (doc_types_raw.get("doc_types") or {}).items():
            try:
                pack.doc_types[name] = DocType.model_validate(spec)
            except ValidationError as exc:
                pack.load_errors[f"doc_types.{name}"] = str(exc)
                logger.error("skipping malformed doc_type %r in pack %r", name, pack_id)

        for path in _glob_yaml(pack_dir / "risk_patterns"):
            try:
                pattern = RiskPattern.model_validate(_read_yaml(path))
                pack.patterns[pattern.id] = pattern
            except (ValidationError, yaml.YAMLError) as exc:
                pack.load_errors[f"risk_patterns/{path.name}"] = str(exc)
                logger.error("skipping malformed risk pattern %s in pack %r", path.name, pack_id)

        boq_raw = _read_yaml(pack_dir / "boq" / "canonical_schema.yaml")
        pack.unit_canon = {
            str(k).strip().lower(): str(v) for k, v in (boq_raw.get("unit_canon") or {}).items()
        }
        if boq_raw.get("checks"):
            pack.boq_checks = pack.boq_checks.model_validate(boq_raw["checks"])

        for path in _glob_yaml(pack_dir / "boq" / "trade_checklists"):
            try:
                checklist = TradeChecklist.model_validate(_read_yaml(path))
                pack.trade_checklists[checklist.id] = checklist
            except (ValidationError, yaml.YAMLError) as exc:
                pack.load_errors[f"trade_checklists/{path.name}"] = str(exc)
                logger.error("skipping malformed checklist %s in pack %r", path.name, pack_id)

        for path in _glob_yaml(pack_dir / "playbooks"):
            playbook = _read_yaml(path)
            pack.playbooks[playbook.get("id", path.stem)] = playbook

        self._cache[pack_id] = pack
        return pack

    def list_patterns(self, pack_id: str, *, validated_only: bool = False) -> list[RiskPattern]:
        """validated_only=True is the paying-user view (spec rulepacks B2)."""
        patterns = self.get_pack(pack_id).patterns.values()
        if validated_only:
            return [p for p in patterns if p.confidence == "validated"]
        return list(patterns)
