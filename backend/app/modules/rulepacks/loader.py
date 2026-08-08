"""Filesystem + database rule-pack loader (spec rulepacks B6, TS-348)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

import yaml
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import bind_workspace_context
from app.modules.rulepacks.schemas import (
    BoqCheckConfig,
    DocType,
    DocumentPrecedence,
    EmployerFamilies,
    NoticeCategory,
    NoticeStandard,
    PackMeta,
    RateSchedule,
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


def _to_uuid(value) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _glob_yaml(directory: Path):
    return sorted(directory.glob("*.yaml")) if directory.is_dir() else []


def _merge_packs(packs: list[RulePack]) -> RulePack | None:
    """Merge multiple rulepacks into one, with later packs overriding earlier ones.

    Use the first pack's meta as the base; overlay all other packs.
    """
    if not packs:
        return None
    if len(packs) == 1:
        return packs[0]

    base = packs[0]
    merged = RulePack(
        meta=base.meta,
        patterns=dict(base.patterns),
        doc_types=dict(base.doc_types),
        expected_documents=list(base.expected_documents),
        unit_canon=dict(base.unit_canon),
        boq_checks=base.boq_checks,
        trade_checklists=dict(base.trade_checklists),
        playbooks=dict(base.playbooks),
        notice_standards={k: v for k, v in base.notice_standards.items()},
        rate_schedules=dict(base.rate_schedules),
        document_precedence=base.document_precedence,
        employer_families=base.employer_families,
        load_errors=dict(base.load_errors),
    )

    for pack in packs[1:]:
        merged.patterns.update(pack.patterns)
        merged.doc_types.update(pack.doc_types)
        merged.expected_documents.extend(
            d for d in pack.expected_documents if d not in merged.expected_documents
        )
        merged.unit_canon.update(pack.unit_canon)
        merged.boq_checks = pack.boq_checks
        merged.trade_checklists.update(pack.trade_checklists)
        merged.playbooks.update(pack.playbooks)
        merged.rate_schedules.update(pack.rate_schedules)
        merged.document_precedence = pack.document_precedence or merged.document_precedence
        merged.employer_families = pack.employer_families or merged.employer_families
        # Merge notice_standards by scope, with later packs overriding categories by key.
        for scope, std in pack.notice_standards.items():
            if scope not in merged.notice_standards:
                merged.notice_standards[scope] = std
            else:
                base_std = merged.notice_standards[scope]
                cats = {c.key: c for c in base_std.categories}
                for cat in std.categories:
                    if cat.key in cats:
                        patch = cat.model_dump(exclude_unset=True)
                        cats[cat.key] = cats[cat.key].model_copy(update=patch)
                    else:
                        cats[cat.key] = cat
                merged.notice_standards[scope] = NoticeStandard(
                    id=std.id or base_std.id,
                    scope=scope,
                    confidence=std.confidence or base_std.confidence,
                    source=(
                        f"{base_std.source}; {std.source}"
                        if base_std.source and std.source
                        else (std.source or base_std.source)
                    ),
                    categories=list(cats.values()),
                )
        merged.load_errors.update(pack.load_errors)

    return merged


class RulePackLoader:
    def __init__(
        self,
        root: Path | str | None = None,
        session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self.root = Path(root) if root else DEFAULT_RULEPACKS_DIR
        # Cache keys: ("db"|"disk", pack_id, workspace_id_str|None).
        # Disk is never keyed by workspace; DB packs are keyed per workspace to avoid
        # serving one customer's active rulepack to another.
        self._cache: dict[tuple[str, str, str | None], RulePack] = {}
        self._session_factory = session_factory

    def set_session_factory(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def list_packs(
        self,
        session: Session | None = None,
        workspace_id: uuid.UUID | str | None = None,
    ) -> list[str]:
        if workspace_id is not None:
            workspace_id = _to_uuid(workspace_id)
        disk_ids = set()
        if self.root.is_dir():
            disk_ids = {p.parent.name for p in self.root.glob("*/pack.yaml")}
        db_ids: set[str] = set()
        try:
            with self._scoped_session(session, workspace_id) as scoped:
                if scoped is None:
                    return sorted(disk_ids)
                stmt = select(self._orm_model.pack_id).where(
                    self._orm_model.is_active.is_(True)
                )
                if workspace_id is not None:
                    stmt = stmt.where(
                        or_(
                            self._orm_model.workspace_id == workspace_id,
                            self._orm_model.workspace_id.is_(None),
                        )
                    )
                rows = scoped.execute(stmt).scalars().all()
                db_ids = set(rows)
        except Exception as exc:
            logger.warning("rulepack db list failed: %s", exc)
        return sorted(disk_ids | db_ids)

    @property
    def _orm_model(self):
        # Imported lazily to avoid circular imports at module load.
        from app.modules.rulepacks.models import RulePack as RulePackRow

        return RulePackRow

    def _cache_key(
        self, pack_id: str, source: str, workspace_id: uuid.UUID | None = None
    ) -> tuple[str, str, str | None]:
        return (source, pack_id, str(workspace_id) if workspace_id else None)

    @contextmanager
    def _scoped_session(
        self, session: Session | None, workspace_id: uuid.UUID | None = None
    ):
        """Use the supplied session or, when a workspace is supplied, create a
        short-lived one with the workspace bound for RLS."""
        if session is not None:
            yield session
            return
        if self._session_factory is None or workspace_id is None:
            yield None
            return
        scoped = self._session_factory()
        try:
            bind_workspace_context(scoped, workspace_id)
            yield scoped
        finally:
            scoped.close()

    def _clear_pack_cache(self, pack_id: str) -> None:
        for key in list(self._cache.keys()):
            if key[1] == pack_id:
                del self._cache[key]

    def invalidate(self, pack_id: str, workspace_id: uuid.UUID | None = None) -> None:
        """Remove a pack from the in-memory cache so activation/deletion changes
        are visible without a server restart."""
        if workspace_id is not None:
            workspace_id = _to_uuid(workspace_id)
        self._clear_pack_cache(pack_id)

    def _disk_pack(self, pack_id: str) -> RulePack | None:
        cache_key = self._cache_key(pack_id, "disk")
        if cache_key in self._cache:
            return self._cache[cache_key]
        pack_dir = self.root / pack_id
        if not pack_dir.is_dir() or not (pack_dir / "pack.yaml").is_file():
            return None
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
            pack.boq_checks = BoqCheckConfig.model_validate(boq_raw["checks"])

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

        for path in _glob_yaml(pack_dir / "notice_standards"):
            try:
                std = NoticeStandard.model_validate(_read_yaml(path))
                pack.notice_standards[std.scope] = std
            except (ValidationError, yaml.YAMLError) as exc:
                pack.load_errors[f"notice_standards/{path.name}"] = str(exc)
                logger.error("skipping malformed notice standard %s in pack %r", path.name, pack_id)

        rates_dir = pack_dir / "rates"
        authority_dirs = (
            sorted(p for p in rates_dir.glob("*") if p.is_dir()) if rates_dir.is_dir() else []
        )
        for authority_dir in authority_dirs:
            for path in _glob_yaml(authority_dir):
                try:
                    schedule = RateSchedule.model_validate(_read_yaml(path))
                    pack.rate_schedules[f"{schedule.authority}/{schedule.year}"] = schedule
                except (ValidationError, yaml.YAMLError) as exc:
                    pack.load_errors[f"rates/{authority_dir.name}/{path.name}"] = str(exc)
                    logger.error(
                        "skipping malformed rate schedule %s in pack %r", path.name, pack_id
                    )

        precedence_path = pack_dir / "document_precedence.yaml"
        if precedence_path.is_file():
            try:
                pack.document_precedence = DocumentPrecedence.model_validate(
                    _read_yaml(precedence_path)
                )
            except (ValidationError, yaml.YAMLError) as exc:
                pack.load_errors["document_precedence.yaml"] = str(exc)
                logger.error("skipping malformed document_precedence in pack %r", pack_id)

        families_path = pack_dir / "employer_families.yaml"
        if families_path.is_file():
            try:
                pack.employer_families = EmployerFamilies.model_validate(
                    _read_yaml(families_path)
                )
            except (ValidationError, yaml.YAMLError) as exc:
                pack.load_errors["employer_families.yaml"] = str(exc)
                logger.error("skipping malformed employer_families in pack %r", pack_id)

        self._cache[cache_key] = pack
        return pack

    def _db_pack(
        self,
        pack_id: str,
        session: Session | None = None,
        workspace_id: uuid.UUID | str | None = None,
    ) -> RulePack | None:
        if workspace_id is not None:
            workspace_id = _to_uuid(workspace_id)
        try:
            with self._scoped_session(session, workspace_id) as scoped:
                if scoped is None:
                    return None
                stmt = (
                    select(self._orm_model)
                    .where(self._orm_model.pack_id == pack_id)
                    .where(self._orm_model.is_active.is_(True))
                )
                if workspace_id is not None:
                    stmt = stmt.where(
                        or_(
                            self._orm_model.workspace_id == workspace_id,
                            self._orm_model.workspace_id.is_(None),
                        )
                    )
                stmt = stmt.order_by(self._orm_model.activated_at.desc())
                row = scoped.execute(stmt).scalars().first()
                if row and row.payload:
                    return RulePack.model_validate(row.payload)
        except Exception as exc:
            logger.warning("rulepack db load failed for %r: %s", pack_id, exc)
        return None

    def get_pack(
        self,
        pack_id: str,
        *,
        reload: bool = False,
        session: Session | None = None,
        workspace_id: uuid.UUID | None = None,
    ) -> RulePack:
        if workspace_id is not None:
            workspace_id = _to_uuid(workspace_id)
        if reload:
            self._clear_pack_cache(pack_id)
        db_key = self._cache_key(pack_id, "db", workspace_id)
        if db_key in self._cache:
            return self._cache[db_key]
        db_pack = self._db_pack(pack_id, session=session, workspace_id=workspace_id)
        if db_pack is not None:
            self._cache[db_key] = db_pack
            return db_pack
        disk_pack = self._disk_pack(pack_id)
        if disk_pack is None:
            # Return a minimal empty pack so callers degrade gracefully.
            return RulePack(
                meta=PackMeta(
                    id=pack_id,
                    version="unknown",
                    jurisdiction="IN",
                    effective_from="",
                )
            )
        return disk_pack

    def get_combined_pack_for_opportunity(
        self,
        session: Session | None = None,
        opportunity_id: uuid.UUID | str | None = None,
        workspace_id: uuid.UUID | str | None = None,
    ) -> RulePack | None:
        """Load all rulepacks applied to an opportunity and merge them."""
        from app.modules.rulepacks.models import OpportunityRulepack

        if workspace_id is not None:
            workspace_id = _to_uuid(workspace_id)
        opp_uuid = _to_uuid(opportunity_id)
        try:
            with self._scoped_session(session, workspace_id) as scoped:
                if scoped is None:
                    return None
                stmt = (
                    select(OpportunityRulepack.rulepack_id)
                    .where(OpportunityRulepack.opportunity_id == opp_uuid)
                    .order_by(OpportunityRulepack.applied_at)
                )
                if workspace_id is not None:
                    stmt = stmt.where(OpportunityRulepack.workspace_id == workspace_id)
                rows = scoped.execute(stmt).scalars().all()
                if not rows:
                    return None
                packs: list[RulePack] = []
                for rid in rows:
                    db_row = scoped.execute(
                        select(self._orm_model).where(self._orm_model.id == _to_uuid(rid))
                    ).scalars().first()
                    if db_row and db_row.payload:
                        packs.append(RulePack.model_validate(db_row.payload))
                    elif db_row:
                        # fallback to disk pack id if stored as pack_id reference
                        pack = self.get_pack(
                            db_row.pack_id,
                            session=scoped,
                            workspace_id=workspace_id,
                        )
                        if pack:
                            packs.append(pack)
                return _merge_packs(packs)
        except Exception as exc:
            logger.warning("rulepack combined load failed for %r: %s", opportunity_id, exc)
        return None

    def notice_standard(
        self,
        pack_id: str,
        region: str | None = None,
        *,
        session: Session | None = None,
        workspace_id: uuid.UUID | None = None,
    ) -> NoticeStandard | None:
        """The universal base standard with the region overlay merged on top
        (spec rulepacks B7 — universal-first, regional refinement). A regional
        category overrides the base category with the same `key`; region-only
        categories are appended. Returns the base alone when no region is given
        or the region has no overlay; None when no standard is defined at all."""
        pack = self.get_pack(pack_id, session=session, workspace_id=workspace_id)
        base = pack.notice_standards.get("universal")
        overlay = pack.notice_standards.get(region) if region else None
        if base is None:
            return overlay
        if overlay is None:
            return base
        merged: dict[str, NoticeCategory] = {c.key: c for c in base.categories}
        for cat in overlay.categories:
            if cat.key in merged:
                # Override ONLY the fields the overlay explicitly set, so an
                # omitted field (e.g. `expected`) keeps the base value rather
                # than reverting to the model default.
                patch = cat.model_dump(exclude_unset=True)
                merged[cat.key] = merged[cat.key].model_copy(update=patch)
            else:
                merged[cat.key] = cat
        return NoticeStandard(
            id=f"{base.id}+{overlay.id}",
            scope=overlay.scope,
            confidence=overlay.confidence,
            source=f"{base.source}; {overlay.source}",
            categories=list(merged.values()),
        )

    def document_precedence(
        self,
        pack_id: str,
        employer_family: str | None = None,
        *,
        session: Session | None = None,
        workspace_id: uuid.UUID | None = None,
    ) -> list[str]:
        """Highest-precedence-first document `kind` order (TS-217). Returns
        `[]` when the pack ships no `document_precedence.yaml` at all — the
        caller (crossref.contradictions) owns the ultimate hardcoded fallback,
        same graceful-absence contract as `rate_schedules`."""
        dp = self.get_pack(pack_id, session=session, workspace_id=workspace_id).document_precedence
        if dp is None:
            return []
        if employer_family and employer_family in dp.employer_family_overrides:
            return list(dp.employer_family_overrides[employer_family])
        return list(dp.default_order)

    def list_patterns(
        self,
        pack_id: str,
        *,
        validated_only: bool = False,
        session: Session | None = None,
        workspace_id: uuid.UUID | None = None,
    ) -> list[RiskPattern]:
        """validated_only=True is the paying-user view (spec rulepacks B2)."""
        patterns = self.get_pack(
            pack_id, session=session, workspace_id=workspace_id
        ).patterns.values()
        if validated_only:
            return [p for p in patterns if p.confidence == "validated"]
        return list(patterns)

    def employer_families(
        self,
        pack_id: str,
        *,
        session: Session | None = None,
        workspace_id: uuid.UUID | None = None,
    ) -> EmployerFamilies | None:
        return self.get_pack(pack_id, session=session, workspace_id=workspace_id).employer_families
