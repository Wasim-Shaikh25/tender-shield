"""Rulepack admin service (TS-348): upload, version, activate, and apply packs."""

from __future__ import annotations

import logging
import tempfile
import uuid
import zipfile
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.storage import StorageBackend, sanitize_filename
from app.modules.rulepacks.loader import RulePackLoader
from app.modules.rulepacks.models import OpportunityRulepack, RulePack, RulePackFile
from app.packsdk.validate import validate_pack

logger = logging.getLogger(__name__)


class RulePackAdminError(Exception):
    def __init__(self, code: str, details: dict | None = None):
        self.code = code
        self.details = details or {}
        super().__init__(code)


def _to_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


class RulePackAdminService:
    def __init__(
        self,
        session: Session,
        *,
        settings,
        loader: RulePackLoader,
        storage: StorageBackend,
    ) -> None:
        self.s = session
        self._settings = settings
        self._loader = loader
        self._storage = storage

    async def upload_pack(
        self,
        archive_bytes: bytes,
        filename: str,
        *,
        scope: str,
        workspace_id: uuid.UUID | None,
        user_id: uuid.UUID,
    ) -> RulePack:
        """Validate, extract, persist source files, and create a draft rulepack."""
        if scope not in {"global", "workspace"}:
            raise RulePackAdminError("invalid_scope")
        if scope == "workspace" and workspace_id is None:
            raise RulePackAdminError("workspace_required")

        if len(archive_bytes) > 100 * 1024 * 1024:
            raise RulePackAdminError("archive_too_large")

        safe_name = sanitize_filename(filename)
        if not safe_name.lower().endswith(".zip"):
            raise RulePackAdminError("archive_must_be_zip")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            archive_path = tmp_root / safe_name
            archive_path.write_bytes(archive_bytes)
            try:
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(tmp_root)
            except zipfile.BadZipFile as exc:
                raise RulePackAdminError("bad_zip_archive") from exc

            # Normalise root: archives may be flat or contain one top-level folder.
            pack_root = self._find_pack_root(tmp_root)
            if pack_root is None:
                raise RulePackAdminError("missing_pack_yaml")
            pack_id = pack_root.name

            report = validate_pack(pack_root, pack_id=pack_id)
            if not report.ok:
                raise RulePackAdminError(
                    "invalid_rulepack",
                    details=report.to_dict(),
                )

            # Build the runtime RulePack from the extracted files.
            loader = RulePackLoader(root=pack_root.parent)
            pack = loader.get_pack(pack_id, reload=True)

            # Persist source files.
            stored_files: list[RulePackFile] = []
            for file_path in pack_root.rglob("*"):
                if not file_path.is_file():
                    continue
                rel = file_path.relative_to(pack_root).as_posix()
                data = file_path.read_bytes()
                storage_key = await self._store_file(data, rel, workspace_id)
                stored_files.append(
                    RulePackFile(
                        id=uuid.uuid4(),
                        rulepack_id=None,  # set after row creation
                        path=rel,
                        storage_key=storage_key,
                        mime_type=self._mime_for_path(rel),
                        size=len(data),
                        checksum=self._sha256(data),
                        workspace_id=_to_uuid(workspace_id),
                    )
                )

            version = self._bump_version_if_needed(
                pack.meta.id, pack.meta.version, scope, workspace_id
            )
            pack.meta.version = version

            row = RulePack(
                id=uuid.uuid4(),
                pack_id=pack.meta.id,
                version=version,
                scope=scope,
                workspace_id=_to_uuid(workspace_id),
                jurisdiction=pack.meta.jurisdiction or "IN",
                is_active=False,
                status="draft",
                meta=pack.meta.model_dump(mode="json"),
                payload=pack.model_dump(mode="json"),
                uploaded_by=_to_uuid(user_id),
            )
            self.s.add(row)
            self.s.flush()
            for f in stored_files:
                f.rulepack_id = row.id
            self.s.add_all(stored_files)
            self.s.commit()
            return row

    def _find_pack_root(self, extracted: Path) -> Path | None:
        candidates = [p for p in extracted.iterdir() if p.is_dir() and (p / "pack.yaml").is_file()]
        if len(candidates) == 1:
            return candidates[0]
        if (extracted / "pack.yaml").is_file():
            return extracted
        # Also allow a single top-level folder that itself contains one pack folder.
        for top in extracted.iterdir():
            if top.is_dir():
                inner = [p for p in top.iterdir() if p.is_dir() and (p / "pack.yaml").is_file()]
                if len(inner) == 1:
                    return inner[0]
        return None

    async def _store_file(
        self, data: bytes, rel_path: str, workspace_id: uuid.UUID | str | None
    ) -> str:
        digest = self._sha256(data)
        safe = sanitize_filename(rel_path)
        prefix = f"workspace/{workspace_id}/" if workspace_id else "rulepacks/"
        key = f"{prefix}{digest[:16]}-{safe}"
        return await self._storage.write(key, data, self._mime_for_path(rel_path))

    def _sha256(self, data: bytes) -> str:
        import hashlib

        return hashlib.sha256(data).hexdigest()

    def _mime_for_path(self, rel: str) -> str:
        import mimetypes

        ext = Path(rel).suffix.lower()
        return mimetypes.types_map.get(ext) or "application/octet-stream"

    def _bump_version_if_needed(
        self, pack_id: str, version: str, scope: str, workspace_id: uuid.UUID | str | None
    ) -> str:
        existing = self.s.execute(
            select(RulePack.id).where(
                RulePack.pack_id == pack_id,
                RulePack.version == version,
                RulePack.scope == scope,
                RulePack.workspace_id == _to_uuid(workspace_id),
            )
        ).scalars().first()
        if existing is None:
            return version
        base = version
        ws_uuid = _to_uuid(workspace_id)
        for n in range(2, 1000):
            candidate = f"{base}-{n}"
            existing = self.s.execute(
                select(RulePack.id).where(
                    RulePack.pack_id == pack_id,
                    RulePack.version == candidate,
                    RulePack.scope == scope,
                    RulePack.workspace_id == ws_uuid,
                )
            ).scalars().first()
            if existing is None:
                return candidate
        raise RulePackAdminError("version_collision")

    def list_packs(
        self,
        *,
        workspace_id: uuid.UUID | None = None,
        include_global: bool = True,
        pack_id: str | None = None,
    ) -> Sequence[RulePack]:
        q = select(RulePack)
        filters = []
        if pack_id:
            filters.append(RulePack.pack_id == pack_id)
        ws_uuid = _to_uuid(workspace_id)
        if include_global:
            if ws_uuid:
                filters.append(
                    ((RulePack.scope == "global") & (RulePack.workspace_id.is_(None)))
                    | (RulePack.workspace_id == ws_uuid)
                )
            else:
                filters.append(RulePack.scope == "global")
                filters.append(RulePack.workspace_id.is_(None))
        elif ws_uuid:
            filters.append(RulePack.workspace_id == ws_uuid)
        if filters:
            q = q.where(*filters)
        return self.s.execute(q.order_by(RulePack.created_at.desc())).scalars().all()

    def activate_pack(self, rulepack_db_id: uuid.UUID | str, user_id: uuid.UUID | str) -> RulePack:
        row = self.s.execute(
            select(RulePack).where(RulePack.id == _to_uuid(rulepack_db_id))
        ).scalars().first()
        if row is None:
            raise RulePackAdminError("not_found")
        # Deactivate other versions of the same pack.
        self.s.execute(
            RulePack.__table__.update()  # type: ignore[attr-defined]
            .where(RulePack.pack_id == row.pack_id)
            .where(RulePack.id != row.id)
            .values(is_active=False, status="deprecated")
        )
        row.is_active = True
        row.status = "active"
        row.activated_at = datetime.now(UTC)
        self.s.commit()
        return row

    def get_pack(self, rulepack_db_id: uuid.UUID | str) -> RulePack | None:
        return self.s.execute(
            select(RulePack).where(RulePack.id == _to_uuid(rulepack_db_id))
        ).scalars().first()

    def get_pack_files(self, rulepack_db_id: uuid.UUID | str) -> Sequence[RulePackFile]:
        return self.s.execute(
            select(RulePackFile).where(RulePackFile.rulepack_id == _to_uuid(rulepack_db_id))
        ).scalars().all()

    def delete_pack(self, rulepack_db_id: uuid.UUID | str) -> None:
        row = self.get_pack(rulepack_db_id)
        if row is None:
            raise RulePackAdminError("not_found")
        self.s.delete(row)
        self.s.commit()

    def apply_packs_to_opportunity(
        self,
        opportunity_id: uuid.UUID | str,
        workspace_id: uuid.UUID | str,
        rulepack_db_ids: list[uuid.UUID | str],
        user_id: uuid.UUID | str,
    ) -> Sequence[OpportunityRulepack]:
        # Validate all ids are visible (global or same workspace).
        opp_uuid = _to_uuid(opportunity_id)
        ws_uuid = _to_uuid(workspace_id)
        ids = [_to_uuid(rid) for rid in rulepack_db_ids]
        packs = self.s.execute(
            select(RulePack).where(RulePack.id.in_(ids))
        ).scalars().all()
        found = {p.id for p in packs}
        missing = set(ids) - found
        if missing:
            raise RulePackAdminError("unknown_rulepack")
        for p in packs:
            if p.scope == "workspace" and p.workspace_id != ws_uuid:
                raise RulePackAdminError("forbidden_rulepack")

        # Clear existing application.
        self.s.execute(
            OpportunityRulepack.__table__.delete()  # type: ignore[attr-defined]
            .where(OpportunityRulepack.opportunity_id == opp_uuid)
            .where(OpportunityRulepack.workspace_id == ws_uuid)
        )
        links: list[OpportunityRulepack] = []
        for rid in rulepack_db_ids:
            links.append(
                OpportunityRulepack(
                    id=uuid.uuid4(),
                    workspace_id=ws_uuid,
                    opportunity_id=opp_uuid,
                    rulepack_id=_to_uuid(rid),
                    applied_by=_to_uuid(user_id),
                )
            )
        self.s.add_all(links)
        self.s.commit()
        return links

    def get_opportunity_packs(
        self, opportunity_id: uuid.UUID | str
    ) -> Sequence[RulePack]:
        rows = self.s.execute(
            select(RulePack)
            .join(
                OpportunityRulepack,
                OpportunityRulepack.rulepack_id == RulePack.id,
            )
            .where(OpportunityRulepack.opportunity_id == _to_uuid(opportunity_id))
            .order_by(OpportunityRulepack.applied_at)
        ).scalars().all()
        return rows

    def to_summary(self, row: RulePack) -> dict:
        return {
            "id": str(row.id),
            "pack_id": row.pack_id,
            "version": row.version,
            "scope": row.scope,
            "workspace_id": str(row.workspace_id) if row.workspace_id else None,
            "jurisdiction": row.jurisdiction,
            "is_active": row.is_active,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "activated_at": row.activated_at.isoformat() if row.activated_at else None,
        }
