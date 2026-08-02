"""ExportService — assembles the Bid Review Pack and enforces the export gate
(Doc §11.4: export blocked until a reviewer completes review). Consumes review,
findings, drafting, ingestion, rulepacks purely via registry capabilities."""

from __future__ import annotations

import hashlib
import uuid
from datetime import date

from sqlalchemy import select

from app.modules.export.models import ReportTemplate
from app.modules.export.render import (
    UNREVIEWED_VARIANT,
    render_docx,
    render_handover_pack,
    render_pdf,
    render_xlsx,
    verify_unreviewed_watermark,
)

FORMATS = {
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    "pdf": ("application/pdf", "pdf"),
}

HANDOVER_FORMATS = {
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    "pdf": ("application/pdf", "pdf"),
}

# Pricing-intel outputs are excluded from Express tiers (express-report spec).
EXPRESS_EXCLUDED_ARTIFACT_KINDS = frozenset({"pricing_loading", "pricing_cashflow"})


class ExportError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ExportService:
    def __init__(
        self,
        session,
        *,
        review_factory=None,
        findings_factory=None,
        drafting_factory=None,
        ingestion_factory=None,
        workspace_factory=None,
        pack_version="in-works",
    ):
        self.s = session
        self._review_factory = review_factory
        self._findings_factory = findings_factory
        self._drafting_factory = drafting_factory
        self._ingestion_factory = ingestion_factory
        self._workspace_factory = workspace_factory
        self._pack_version = pack_version

    def _gate_ok(self, workspace_id, opportunity_id) -> bool:
        if self._review_factory is None:
            return False
        gate = self._review_factory(self.s).gate(workspace_id, opportunity_id)
        return gate.get("export_allowed", False)

    def _findings(self, workspace_id, opportunity_id) -> list[dict]:
        if self._findings_factory is None:
            return []
        return [
            {
                "severity": r.severity,
                "category": r.category,
                "title": r.title,
                "review_status": r.review_status,
                "source_page": r.source_page,
                "source_quote": r.source_quote,
            }
            for r in self._findings_factory(self.s).list(workspace_id, opportunity_id)
        ]

    def _artifacts(self, workspace_id, opportunity_id) -> list[dict]:
        if self._drafting_factory is None:
            return []
        return [
            {"kind": a.kind, "version": a.version, "body": a.body}
            for a in self._drafting_factory(self.s).list(workspace_id, opportunity_id)
        ]

    def _express_artifacts(self, workspace_id, opportunity_id) -> list[dict]:
        return [
            a
            for a in self._artifacts(workspace_id, opportunity_id)
            if a.get("kind") not in EXPRESS_EXCLUDED_ARTIFACT_KINDS
        ]

    def _title(self, workspace_id, opportunity_id) -> str:
        if self._ingestion_factory is None:
            return "this tender"
        opp = self._ingestion_factory(self.s).get_opportunity(workspace_id, opportunity_id)
        return opp.title if opp else "this tender"

    def _reviewer_meta(self, workspace_id, opportunity_id) -> dict[str, str]:
        if self._review_factory is None:
            return {}
        last = self._review_factory(self.s).last_reviewer(workspace_id, opportunity_id)
        if not last:
            return {}
        reviewed_at = last["reviewed_at"]
        reviewed_at_str = reviewed_at.isoformat() if reviewed_at else ""
        meta = {"reviewed_at": reviewed_at_str}
        reviewer_id = last.get("reviewer_id")
        if reviewer_id and self._workspace_factory:
            user = self._workspace_factory(self.s).get_user(reviewer_id)
            if user:
                meta["reviewed_by_email"] = user["email"]
        return meta

    def _template(self, workspace_id, template_id: str | None = None) -> dict | None:
        ws = uuid.UUID(str(workspace_id))
        if template_id:
            row = self.s.scalar(
                select(ReportTemplate).where(
                    ReportTemplate.id == uuid.UUID(str(template_id)),
                    ReportTemplate.workspace_id == ws,
                )
            )
            return self._template_row_to_dict(row) if row else None
        row = self.s.scalar(
            select(ReportTemplate).where(
                ReportTemplate.workspace_id == ws,
                ReportTemplate.is_default.is_(True),
            )
        )
        return self._template_row_to_dict(row) if row else None

    @staticmethod
    def _template_row_to_dict(row: ReportTemplate | None) -> dict | None:
        if row is None:
            return None
        return {
            "id": str(row.id),
            "name": row.name,
            "is_default": row.is_default,
            "primary_color": row.primary_color,
            "accent_color": row.accent_color,
            "logo_url": row.logo_url,
            "watermark_text": row.watermark_text,
            "footer_text": row.footer_text,
            "report_title": row.report_title,
        }

    def _render(
        self,
        fmt: str,
        title: str,
        workspace_id,
        opportunity_id,
        meta: dict,
        *,
        unreviewed: bool = False,
        template: dict | None = None,
    ) -> bytes:
        findings = self._findings(workspace_id, opportunity_id)
        artifacts = (
            self._express_artifacts(workspace_id, opportunity_id)
            if unreviewed
            else self._artifacts(workspace_id, opportunity_id)
        )
        if fmt == "xlsx":
            return render_xlsx(title, findings, meta, template)
        if fmt == "pdf":
            return render_pdf(title, artifacts, findings, meta, template)
        return render_docx(title, artifacts, findings, meta, template)

    def export(
        self, workspace_id, opportunity_id, fmt: str, template_id: str | None = None
    ) -> tuple[str, str, bytes]:
        if fmt not in FORMATS:
            raise ExportError("bad_format")
        if not self._gate_ok(workspace_id, opportunity_id):
            raise ExportError("review_incomplete")  # Doc §11.4 — the export gate

        title = self._title(workspace_id, opportunity_id)
        meta = {
            "date": date.today().isoformat(),
            "pack": self._pack_version,
        }
        meta.update(self._reviewer_meta(workspace_id, opportunity_id))
        template = self._template(workspace_id, template_id)

        media_type, ext = FORMATS[fmt]
        draft = self._render(
            fmt, title, workspace_id, opportunity_id, meta, template=template
        )
        meta["integrity_hash"] = hashlib.sha256(draft).hexdigest()
        data = self._render(
            fmt, title, workspace_id, opportunity_id, meta, template=template
        )

        filename = f"bid-review-pack-{opportunity_id}.{ext}"
        return filename, media_type, data

    def export_unreviewed(
        self, workspace_id, opportunity_id, fmt: str, template_id: str | None = None
    ) -> tuple[str, str, bytes]:
        """Express lane export — bypasses review gate, watermarks every format."""
        if fmt not in FORMATS:
            raise ExportError("bad_format")

        title = self._title(workspace_id, opportunity_id)
        meta = {
            "date": date.today().isoformat(),
            "pack": self._pack_version,
            "variant": UNREVIEWED_VARIANT,
        }
        template = self._template(workspace_id, template_id)

        media_type, ext = FORMATS[fmt]
        draft = self._render(
            fmt, title, workspace_id, opportunity_id, meta, unreviewed=True, template=template
        )
        meta["integrity_hash"] = hashlib.sha256(draft).hexdigest()
        data = self._render(
            fmt, title, workspace_id, opportunity_id, meta, unreviewed=True, template=template
        )

        if not verify_unreviewed_watermark(fmt, data):
            raise ExportError("watermark_missing")

        filename = f"express-report-{opportunity_id}.{ext}"
        return filename, media_type, data

    def export_handover(
        self,
        workspace_id,
        opportunity_id: str,
        fmt: str,
        handover: dict,
        *,
        view: str = "full",
        template_id: str | None = None,
    ) -> tuple[str, str, bytes]:
        if fmt not in HANDOVER_FORMATS:
            raise ExportError("bad_format")
        title = handover.get("opportunity", {}).get("title") or "this tender"
        meta = {
            "date": date.today().isoformat(),
            "pack": self._pack_version,
            "integrity_hash": handover.get("sealed_hash", ""),
            "view": view,
        }
        template = self._template(workspace_id, template_id)
        data = render_handover_pack(title, handover, fmt, meta, template)
        # Re-render so the hash in the stamp is over the final bytes.
        meta["integrity_hash"] = hashlib.sha256(data).hexdigest()
        data = render_handover_pack(title, handover, fmt, meta, template)

        media_type, ext = HANDOVER_FORMATS[fmt]
        suffix = f"-{view}" if view and view != "full" else ""
        filename = f"handover-pack-{opportunity_id}{suffix}.{ext}"
        return filename, media_type, data

    # ---- branded report templates (TS-331) --------------------------------
    def list_templates(self, workspace_id) -> list[dict]:
        ws = uuid.UUID(str(workspace_id))
        rows = self.s.scalars(
            select(ReportTemplate).where(ReportTemplate.workspace_id == ws)
        ).all()
        return [self._template_row_to_dict(r) for r in rows]

    def get_template(self, workspace_id, template_id: str) -> dict | None:
        return self._template(workspace_id, template_id)

    def create_template(
        self, workspace_id, fields: dict
    ) -> dict:
        ws = uuid.UUID(str(workspace_id))
        if fields.get("is_default"):
            self.s.query(ReportTemplate).filter(
                ReportTemplate.workspace_id == ws
            ).update({"is_default": False})
        row = ReportTemplate(workspace_id=ws, **fields)
        self.s.add(row)
        self.s.commit()
        return self._template_row_to_dict(row)

    def update_template(
        self, workspace_id, template_id: str, fields: dict
    ) -> dict | None:
        ws = uuid.UUID(str(workspace_id))
        row = self.s.scalar(
            select(ReportTemplate).where(
                ReportTemplate.id == uuid.UUID(str(template_id)),
                ReportTemplate.workspace_id == ws,
            )
        )
        if row is None:
            return None
        if fields.get("is_default"):
            self.s.query(ReportTemplate).filter(
                ReportTemplate.workspace_id == ws
            ).update({"is_default": False})
        for key, value in fields.items():
            setattr(row, key, value)
        self.s.commit()
        return self._template_row_to_dict(row)

    def delete_template(self, workspace_id, template_id: str) -> bool:
        ws = uuid.UUID(str(workspace_id))
        row = self.s.scalar(
            select(ReportTemplate).where(
                ReportTemplate.id == uuid.UUID(str(template_id)),
                ReportTemplate.workspace_id == ws,
            )
        )
        if row is None:
            return False
        self.s.delete(row)
        self.s.commit()
        return True

    def set_default_template(self, workspace_id, template_id: str) -> dict | None:
        ws = uuid.UUID(str(workspace_id))
        target = uuid.UUID(str(template_id))
        self.s.query(ReportTemplate).filter(
            ReportTemplate.workspace_id == ws
        ).update({"is_default": False})
        row = self.s.scalar(
            select(ReportTemplate).where(
                ReportTemplate.id == target,
                ReportTemplate.workspace_id == ws,
            )
        )
        if row is None:
            return None
        row.is_default = True
        self.s.commit()
        return self._template_row_to_dict(row)
