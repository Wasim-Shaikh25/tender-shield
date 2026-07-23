"""ExportService — assembles the Bid Review Pack and enforces the export gate
(Doc §11.4: export blocked until a reviewer completes review). Consumes review,
findings, drafting, ingestion, rulepacks purely via registry capabilities."""

from __future__ import annotations

from datetime import date

from app.modules.export.render import render_docx, render_xlsx

FORMATS = {
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
}


class ExportError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ExportService:
    def __init__(self, session, *, review_factory=None, findings_factory=None,
                 drafting_factory=None, ingestion_factory=None, pack_version="in-works"):
        self.s = session
        self._review_factory = review_factory
        self._findings_factory = findings_factory
        self._drafting_factory = drafting_factory
        self._ingestion_factory = ingestion_factory
        self._pack_version = pack_version

    def _gate_ok(self, org_id, opportunity_id) -> bool:
        if self._review_factory is None:
            return False
        gate = self._review_factory(self.s).gate(org_id, opportunity_id)
        return gate.get("export_allowed", False)

    def _findings(self, org_id, opportunity_id) -> list[dict]:
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
            for r in self._findings_factory(self.s).list(org_id, opportunity_id)
        ]

    def _artifacts(self, org_id, opportunity_id) -> list[dict]:
        if self._drafting_factory is None:
            return []
        return [
            {"kind": a.kind, "version": a.version, "body": a.body}
            for a in self._drafting_factory(self.s).list(org_id, opportunity_id)
        ]

    def _title(self, org_id, opportunity_id) -> str:
        if self._ingestion_factory is None:
            return "this tender"
        opp = self._ingestion_factory(self.s).get_opportunity(org_id, opportunity_id)
        return opp.title if opp else "this tender"

    def export(self, org_id, opportunity_id, fmt: str) -> tuple[str, str, bytes]:
        if fmt not in FORMATS:
            raise ExportError("bad_format")
        if not self._gate_ok(org_id, opportunity_id):
            raise ExportError("review_incomplete")  # Doc §11.4 — the export gate

        title = self._title(org_id, opportunity_id)
        findings = self._findings(org_id, opportunity_id)
        meta = {"date": date.today().isoformat(), "pack": self._pack_version}
        media_type, ext = FORMATS[fmt]

        if fmt == "xlsx":
            data = render_xlsx(title, findings, meta)
        else:
            data = render_docx(title, self._artifacts(org_id, opportunity_id), findings, meta)

        filename = f"bid-review-pack-{opportunity_id}.{ext}"
        return filename, media_type, data
