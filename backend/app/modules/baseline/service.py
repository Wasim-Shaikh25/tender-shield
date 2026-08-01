"""BaselineService — freeze the reviewed commercial state into an immutable,
hash-sealed baseline and derive the notice register, award-vs-tender delta and
handover pack.

Consumes findings/review/ingestion purely via injected registry capabilities —
it never imports those modules (CLAUDE.md §2)."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.modules.baseline.compare_award import diff_boq, diff_clauses, diff_findings
from app.modules.baseline.cost_codes import (
    boq_assumption_findings,
    build_tree,
    code_dict,
    compute_exposure_totals,
    finance_notice_windows,
    lock_timestamp,
    mapping_dict,
    scope_gap_findings,
    snapshot_cost_codes,
)
from app.modules.baseline.handover_views import filter_handover
from app.modules.baseline.models import (
    AwardDocument,
    Baseline,
    CostCode,
    CostCodeMapping,
    NoticeContact,
    WatchlistControl,
)
from app.modules.baseline.notice_register import enrich_rule
from app.modules.baseline.notices import extract_notice_rules
from app.modules.baseline.watchlist import (
    apply_cadence,
    control_dict,
    seed_watchlist,
)

_ACCEPTED = {"accepted", "edited"}


class BaselineError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class BaselineService:
    def __init__(
        self,
        session: Session,
        *,
        findings_factory: Callable | None = None,
        review_factory: Callable | None = None,
        ingestion_factory: Callable | None = None,
        segment_clauses_fn: Callable[[str], list] | None = None,
        loader_provider: Callable[[], object | None] = lambda: None,
        standards_factory: Callable | None = None,
        export_factory: Callable | None = None,
        approval_matrix_factory: Callable | None = None,
        publish: Callable[[str, dict], object] = lambda event, payload: None,
        pack_id: str = "in-works",
    ):
        self.s = session
        self._findings_factory = findings_factory
        self._review_factory = review_factory
        self._ingestion_factory = ingestion_factory
        self._segment_clauses_fn = segment_clauses_fn
        self._loader_provider = loader_provider
        self._standards_factory = standards_factory
        self._export_factory = export_factory
        self._approval_matrix_factory = approval_matrix_factory
        self._publish = publish
        self._pack_id = pack_id

    def _require_approval(
        self, workspace_id, *, role: str, action: str, amount_minor: int = 0
    ) -> None:
        if self._approval_matrix_factory is None:
            return
        matrix = self._approval_matrix_factory(self.s)
        decision = matrix.check(
            workspace_id, role=role, action=action, amount_minor=amount_minor
        )
        if not decision.allowed:
            raise BaselineError("approval_denied")

    def _notice_contacts_map(self, workspace_id, opportunity_id) -> dict[str, NoticeContact]:
        rows = self.s.scalars(
            select(NoticeContact).where(
                NoticeContact.workspace_id == uuid.UUID(str(workspace_id)),
                NoticeContact.opportunity_id == uuid.UUID(str(opportunity_id)),
            )
        ).all()
        return {row.notice_type: row for row in rows}

    def _enrich_notice_rules(
        self,
        workspace_id,
        opportunity_id,
        rules: list[dict],
        *,
        region: str | None,
    ) -> list[dict]:
        categories = self._effective_categories(workspace_id, region)
        contacts = self._notice_contacts_map(workspace_id, opportunity_id)
        deadlines = self._confirmed_deadlines(workspace_id, opportunity_id)
        return [
            enrich_rule(
                rule,
                categories=categories,
                contacts=contacts,
                deadlines=deadlines,
            )
            for rule in rules
        ]

    # ---- reads from other modules (capabilities only) ---------------------
    def _accepted_findings(self, workspace_id, opportunity_id) -> list[dict]:
        if self._findings_factory is None:
            raise BaselineError("findings_unavailable")
        rows = self._findings_factory(self.s).list(workspace_id, opportunity_id)
        return [
            {
                "id": str(r.id),
                "kind": r.kind,
                "category": r.category,
                "severity": r.severity,
                "title": r.title,
                "detail": r.detail,
                "source_page": r.source_page,
                "source_quote": r.source_quote,
                "suggested_action": r.suggested_action,
                "amount_exposure": r.amount_exposure,
                "currency": r.currency,
                "pattern_id": r.pattern_id,
                "document_id": str(r.document_id) if r.document_id else None,
                "review_status": r.review_status,
            }
            for r in rows
            if r.review_status in _ACCEPTED
        ]

    def _award_text(self, workspace_id, opportunity_id) -> str:
        """Return the parsed text of the most recently uploaded award letter, if any."""
        doc = self.s.scalar(
            select(AwardDocument)
            .where(
                AwardDocument.workspace_id == uuid.UUID(str(workspace_id)),
                AwardDocument.opportunity_id == uuid.UUID(str(opportunity_id)),
            )
            .order_by(AwardDocument.created_at.desc())
        )
        return doc.text if doc else ""

    def _award_findings(self, award_text: str) -> list[dict]:
        """Turn award text into a synthetic finding so notice extraction can run on it."""
        if not award_text:
            return []
        return [
            {
                "category": "award",
                "title": "Award letter",
                "detail": award_text[:2000],
                "source_quote": award_text[:200],
                "source_page": None,
            }
        ]

    def _confirmed_deadlines(self, workspace_id, opportunity_id) -> list[dict]:
        if self._ingestion_factory is None:
            return []
        svc = self._ingestion_factory(self.s)
        out = []
        for d in svc.list_deadlines(workspace_id, opportunity_id):
            if not d.confirmed:
                continue
            out.append(
                {
                    "kind": d.kind,
                    "due_at": d.due_at.isoformat() if d.due_at else None,
                    "description": d.description,
                    "source_page": d.source_page,
                    "source_quote": d.source_quote,
                }
            )
        return out

    def _clause_records(self, workspace_id, opportunity_id) -> list[dict]:
        """Segmented clauses mapped to the shape extract_notice_rules consumes,
        so the notice register reads the actual contract text — not only what
        the risk engine flagged (works with no LLM configured)."""
        if self._ingestion_factory is None:
            return []
        svc = self._ingestion_factory(self.s)
        lister = getattr(svc, "list_clauses", None)
        if lister is None:
            return []
        out = []
        for c in lister(workspace_id, opportunity_id):
            text = c.text or ""
            out.append(
                {
                    "category": "clause",
                    "title": c.clause_ref or "clause",
                    "detail": text,
                    "source_quote": text[:200],
                    "source_page": c.page_from,
                }
            )
        return out

    def _segment_clause_dicts(self, text: str) -> list[dict]:
        if self._segment_clauses_fn is None:
            raise BaselineError("ingestion_unavailable")
        return [
            {
                "clause_ref": seg.clause_ref,
                "heading": seg.heading,
                "text": seg.text,
                "page_from": seg.page_from,
            }
            for seg in self._segment_clauses_fn(text)
        ]

    def _rulepack_categories(self, region: str | None) -> list[dict]:
        """Universal base + regional overlay from the rulepack loader, as dicts
        tagged origin='standard'. Empty when rulepacks is disabled — the module
        then degrades to extraction-only (spec baseline B8)."""
        loader = self._loader_provider()
        if loader is None:
            return []
        getter = getattr(loader, "notice_standard", None)
        if getter is None:
            return []
        standard = getter(self._pack_id, region)
        if standard is None:
            return []
        out = []
        for c in standard.categories:
            d = c.model_dump()
            d["origin"] = "standard"
            out.append(d)
        return out

    def _org_overlay(self, workspace_id) -> dict | None:
        """The org's custom notice standard (mode + categories) via capability."""
        if self._standards_factory is None:
            return None
        return self._standards_factory(self.s).get_notice(workspace_id)

    def _effective_categories(self, workspace_id, region: str | None) -> list[dict]:
        """The three-layer merge: universal + regional (rulepack) then the org's
        custom standard on top (spec standards B1). `prevail` overrides matching
        keys; `side_by_side` appends the org regimes alongside so both show."""
        cats = self._rulepack_categories(region)
        overlay = self._org_overlay(workspace_id)
        if not overlay or not overlay.get("categories"):
            return cats
        mode = overlay.get("mode", "prevail")
        by_key = {c["key"]: i for i, c in enumerate(cats)}
        for oc in overlay["categories"]:
            entry = {**oc, "origin": "org"}
            if mode == "prevail" and oc["key"] in by_key:
                # Workspace values win, but keep base fields the org omitted.
                merged = {**cats[by_key[oc["key"]]], **oc, "origin": "org"}
                cats[by_key[oc["key"]]] = merged
            else:
                # side_by_side, or a brand-new org-only regime: append.
                cats.append(entry)
        return cats

    @staticmethod
    def _classify(rule: dict, categories: list[dict]) -> str:
        """Assign a semantic notice category to an extracted rule by matching the
        effective standard's keywords against its text — deterministic (B4/B8)."""
        if not categories:
            return rule.get("category", "clause")
        blob = f"{rule.get('trigger', '')} {rule.get('source_quote', '')}".lower()
        for cat in categories:
            if any(kw.lower() in blob for kw in (cat.get("keywords") or [])):
                return cat["key"]
        return rule.get("category", "clause")

    def _notice_analysis(
        self, workspace_id, opportunity_id, findings: list[dict], region: str | None
    ):
        records = findings + self._clause_records(workspace_id, opportunity_id)
        categories = self._effective_categories(workspace_id, region)
        rules = []
        for r in extract_notice_rules(records):
            d = r.as_dict()
            d["category"] = self._classify(d, categories)
            rules.append(d)
        found_keys = {r["category"] for r in rules}
        gaps = []
        std_categories = []
        seen_gap_keys: set[str] = set()
        for cat in categories:
            std_categories.append(
                {
                    "key": cat["key"],
                    "label": cat.get("label", cat["key"]),
                    "typical_days": cat.get("typical_days"),
                    "origin": cat.get("origin", "standard"),
                }
            )
            # Deterministic gap: an expected regime with no matching window in
            # the contract — the analogue of risk absence detection.
            key = cat["key"]
            if cat.get("expected") and key not in found_keys and key not in seen_gap_keys:
                seen_gap_keys.add(key)
                gaps.append(
                    {
                        "key": cat["key"],
                        "label": cat.get("label", cat["key"]),
                        "typical_days": cat.get("typical_days"),
                        "note": cat.get("note"),
                        "origin": cat.get("origin", "standard"),
                    }
                )
        return {
            "region": region,
            "rules": rules,
            "gaps": gaps,
            "standard_categories": std_categories,
        }

    def _opportunity_meta(self, workspace_id, opportunity_id) -> dict:
        if self._ingestion_factory is None:
            return {"id": str(opportunity_id), "title": "this tender"}
        opp = self._ingestion_factory(self.s).get_opportunity(workspace_id, opportunity_id)
        if opp is None:
            raise BaselineError("opportunity_not_found")
        return {
            "id": str(opp.id),
            "title": opp.title,
            "employer": opp.employer,
            "employer_family": opp.employer_family,
            "contract_form": opp.contract_form,
            "jurisdiction": opp.jurisdiction,
        }

    def _gate_ok(self, workspace_id, opportunity_id) -> None:
        """Freeze is blocked until review completes (spec B1, Doc §11.4)."""
        if self._review_factory is None:
            raise BaselineError("review_unavailable")
        gate = self._review_factory(self.s).gate(workspace_id, opportunity_id)
        if not gate.get("export_allowed", False):
            raise BaselineError("review_incomplete")

    # ---- snapshot + hashing ----------------------------------------------
    def _build_snapshot(
        self, workspace_id, opportunity_id, source: str, award_text: str = ""
    ) -> dict:
        findings = self._accepted_findings(workspace_id, opportunity_id)
        if source == "award":
            award_text = award_text or self._award_text(workspace_id, opportunity_id)
            findings = findings + self._award_findings(award_text)
        deadlines = self._confirmed_deadlines(workspace_id, opportunity_id)
        clauses = self._clause_records(workspace_id, opportunity_id)
        meta = self._opportunity_meta(workspace_id, opportunity_id)
        analysis = self._notice_analysis(
            workspace_id, opportunity_id, findings, meta.get("jurisdiction")
        )
        snapshot = {
            "source": source,
            "opportunity": meta,
            "findings": findings,
            "clauses": clauses,
            "deadlines": deadlines,
            "notice_rules": analysis["rules"],
            "notice_gaps": analysis["gaps"],
            "notice_region": analysis["region"],
            "counts": {
                "findings": len(findings),
                "clauses": len(clauses),
                "deadlines": len(deadlines),
                "notice_rules": len(analysis["rules"]),
                "notice_gaps": len(analysis["gaps"]),
            },
        }
        if source == "award":
            snapshot["award_text_preview"] = award_text[:500]
        cost_payload = self._cost_code_payload(workspace_id, opportunity_id)
        if cost_payload["codes"]:
            snapshot["cost_codes"] = cost_payload["snapshot"]
            snapshot["counts"]["cost_codes"] = len(cost_payload["codes"])
        return snapshot

    def store_award_document(
        self, workspace_id, opportunity_id, filename: str, data: bytes, uploaded_by=None
    ) -> AwardDocument:
        """Parse an award letter and persist its text for the award baseline."""
        if self._ingestion_factory is None:
            raise BaselineError("ingestion_unavailable")
        text = self._ingestion_factory(self.s).extract_text(filename, data)
        doc = AwardDocument(
            workspace_id=uuid.UUID(str(workspace_id)),
            opportunity_id=uuid.UUID(str(opportunity_id)),
            filename=filename,
            text=text,
            sha256=hashlib.sha256(data).hexdigest(),
            uploaded_by=uuid.UUID(str(uploaded_by)) if uploaded_by else None,
        )
        self.s.add(doc)
        self.s.commit()
        return doc

    @staticmethod
    def _hash(snapshot: dict) -> str:
        """SHA-256 over the canonical snapshot (excludes volatile sealed_at,
        which is not part of the snapshot dict) — the seal (spec B3)."""
        canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # ---- freeze / read ----------------------------------------------------
    def freeze(
        self, workspace_id, opportunity_id, *, source="tender", note=None, sealer_id=None
    ):
        if source not in {"tender", "award"}:
            raise BaselineError("bad_source")
        self._gate_ok(workspace_id, opportunity_id)
        snapshot = self._build_snapshot(workspace_id, opportunity_id, source)
        opp = uuid.UUID(str(opportunity_id))
        # Compute the next version atomically inside the insert so concurrent
        # freezes cannot race on the same opportunity.
        next_version_expr = (
            select(func.coalesce(func.max(Baseline.version), 0) + 1)
            .where(Baseline.opportunity_id == opp)
            .scalar_subquery()
        )
        stmt = (
            insert(Baseline)
            .values(
                workspace_id=uuid.UUID(str(workspace_id)),
                opportunity_id=opp,
                version=next_version_expr,
                source=source,
                content_sha256=self._hash(snapshot),
                snapshot=snapshot,
                note=note,
                sealed_by=uuid.UUID(str(sealer_id)) if sealer_id else None,
            )
            .returning(Baseline)
        )
        row = self.s.scalars(stmt).one()
        self.s.commit()
        # Audit the seal through the review module's append-only log if present.
        if self._review_factory is not None:
            self._review_factory(self.s).audit(
                workspace_id,
                actor=sealer_id,
                action="baseline.sealed",
                object_type="baseline",
                object_id=row.id,
                detail={"version": row.version, "source": source, "hash": row.content_sha256},
            )
        self._publish(
            "baseline.sealed",
            {
                "workspace_id": str(workspace_id),
                "opportunity_id": str(opp),
                "baseline_id": str(row.id),
                "version": row.version,
                "source": source,
            },
        )
        seed_watchlist(
            self.s,
            workspace_id=workspace_id,
            opportunity_id=opp,
            baseline_id=row.id,
            findings=snapshot.get("findings", []),
        )
        self._lock_cost_codes(workspace_id, opportunity_id)
        if snapshot.get("cost_codes"):
            self._publish(
                "baseline.cost_codes_locked",
                {
                    "workspace_id": str(workspace_id),
                    "opportunity_id": str(opp),
                    "baseline_id": str(row.id),
                    "count": len(snapshot["cost_codes"]),
                },
            )
        return row

    def list(self, workspace_id, opportunity_id) -> list[Baseline]:
        return list(
            self.s.scalars(
                select(Baseline)
                .where(
                    Baseline.workspace_id == uuid.UUID(str(workspace_id)),
                    Baseline.opportunity_id == uuid.UUID(str(opportunity_id)),
                )
                .order_by(Baseline.version.desc())
            )
        )

    def get(self, workspace_id, baseline_id) -> Baseline | None:
        return self.s.scalar(
            select(Baseline).where(
                Baseline.id == uuid.UUID(str(baseline_id)),
                Baseline.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )

    def latest(self, workspace_id, opportunity_id, *, source: str | None = None) -> Baseline | None:
        stmt = select(Baseline).where(
            Baseline.workspace_id == uuid.UUID(str(workspace_id)),
            Baseline.opportunity_id == uuid.UUID(str(opportunity_id)),
        )
        if source is not None:
            stmt = stmt.where(Baseline.source == source)
        return self.s.scalar(stmt.order_by(Baseline.version.desc()))

    def verify(self, workspace_id, baseline_id) -> dict:
        row = self.get(workspace_id, baseline_id)
        if row is None:
            raise BaselineError("not_found")
        recomputed = self._hash(row.snapshot)
        return {
            "baseline_id": str(row.id),
            "version": row.version,
            "intact": recomputed == row.content_sha256,
            "sealed_hash": row.content_sha256,
            "recomputed_hash": recomputed,
        }

    # ---- derived views ----------------------------------------------------
    def notice_register(self, workspace_id, opportunity_id) -> dict:
        """The notice-rule register from the latest sealed baseline; falls back
        to the live accepted findings when nothing is sealed yet."""
        latest = self.latest(workspace_id, opportunity_id)
        if latest is not None:
            snap = latest.snapshot
            region = snap.get("notice_region")
            rules = self._enrich_notice_rules(
                workspace_id,
                opportunity_id,
                snap.get("notice_rules", []),
                region=region,
            )
            return {
                "source": "baseline",
                "version": latest.version,
                "region": region,
                "rules": rules,
                "gaps": snap.get("notice_gaps", []),
                "contacts": [
                    self._contact_dict(row)
                    for row in self._notice_contacts_map(workspace_id, opportunity_id).values()
                ],
            }
        findings = self._accepted_findings(workspace_id, opportunity_id)
        meta = self._opportunity_meta(workspace_id, opportunity_id)
        analysis = self._notice_analysis(
            workspace_id, opportunity_id, findings, meta.get("jurisdiction")
        )
        rules = self._enrich_notice_rules(
            workspace_id,
            opportunity_id,
            analysis["rules"],
            region=analysis["region"],
        )
        return {
            "source": "live",
            "version": None,
            "region": analysis["region"],
            "rules": rules,
            "gaps": analysis["gaps"],
            "contacts": [
                self._contact_dict(row)
                for row in self._notice_contacts_map(workspace_id, opportunity_id).values()
            ],
        }

    @staticmethod
    def _contact_dict(row: NoticeContact) -> dict:
        return {
            "id": str(row.id),
            "notice_type": row.notice_type,
            "party": row.party,
            "role_label": row.role_label,
            "authorized_representative": row.authorized_representative,
            "postal_address": row.postal_address,
            "email": row.email,
            "required_content": row.required_content or [],
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def upsert_notice_contacts(
        self,
        workspace_id,
        opportunity_id,
        contacts: list[dict],
        *,
        actor_user_id,
        actor_role: str,
    ) -> list[dict]:
        self._require_approval(
            workspace_id, role=actor_role, action="notice_contacts_edit"
        )
        wid = uuid.UUID(str(workspace_id))
        oid = uuid.UUID(str(opportunity_id))
        existing = self._notice_contacts_map(workspace_id, opportunity_id)
        out: list[NoticeContact] = []
        for entry in contacts:
            notice_type = entry["notice_type"]
            row = existing.get(notice_type)
            if row is None:
                row = NoticeContact(
                    workspace_id=wid,
                    opportunity_id=oid,
                    notice_type=notice_type,
                )
                self.s.add(row)
            row.party = entry.get("party", row.party or "employer")
            row.role_label = entry.get("role_label")
            row.authorized_representative = entry.get("authorized_representative")
            row.postal_address = entry.get("postal_address")
            row.email = entry.get("email")
            row.required_content = entry.get("required_content")
            row.updated_by = uuid.UUID(str(actor_user_id)) if actor_user_id else None
            out.append(row)
        self.s.commit()
        for row in out:
            self.s.refresh(row)
        self._publish(
            "baseline.notice_contacts_updated",
            {
                "workspace_id": str(workspace_id),
                "opportunity_id": str(opportunity_id),
                "count": len(out),
            },
        )
        return [self._contact_dict(row) for row in out]

    def _cost_codes_locked(self, workspace_id, opportunity_id) -> bool:
        return self.latest(workspace_id, opportunity_id) is not None

    def _cost_code_rows(self, workspace_id, opportunity_id) -> list[CostCode]:
        return list(
            self.s.scalars(
                select(CostCode)
                .where(
                    CostCode.workspace_id == uuid.UUID(str(workspace_id)),
                    CostCode.opportunity_id == uuid.UUID(str(opportunity_id)),
                )
                .order_by(CostCode.code)
            )
        )

    def _mapping_rows(self, workspace_id, opportunity_id) -> list[CostCodeMapping]:
        return list(
            self.s.scalars(
                select(CostCodeMapping).where(
                    CostCodeMapping.workspace_id == uuid.UUID(str(workspace_id)),
                    CostCodeMapping.opportunity_id == uuid.UUID(str(opportunity_id)),
                )
            )
        )

    def _cost_code_payload(self, workspace_id, opportunity_id) -> dict:
        codes = self._cost_code_rows(workspace_id, opportunity_id)
        mappings = self._mapping_rows(workspace_id, opportunity_id)
        mapping_dicts = [mapping_dict(row) for row in mappings]
        code_dicts = [
            code_dict(row, mappings=[m for m in mapping_dicts if m["cost_code_id"] == str(row.id)])
            for row in codes
        ]
        return {
            "codes": code_dicts,
            "mappings": mapping_dicts,
            "tree": build_tree(code_dicts),
            "snapshot": snapshot_cost_codes(code_dicts, mapping_dicts),
        }

    def list_cost_codes(self, workspace_id, opportunity_id) -> dict:
        payload = self._cost_code_payload(workspace_id, opportunity_id)
        findings = self._accepted_findings(workspace_id, opportunity_id)
        payload["exposure_totals"] = compute_exposure_totals(findings, payload["mappings"])
        payload["locked"] = self._cost_codes_locked(workspace_id, opportunity_id)
        return payload

    def upsert_cost_codes(
        self,
        workspace_id,
        opportunity_id,
        *,
        codes: list[dict],
        mappings: list[dict],
        actor_role: str = "estimator",
    ) -> dict:
        if self._cost_codes_locked(workspace_id, opportunity_id):
            self._require_approval(workspace_id, role=actor_role, action="cost_code_edit")
        wid = uuid.UUID(str(workspace_id))
        oid = uuid.UUID(str(opportunity_id))
        existing_codes = {
            str(row.id): row for row in self._cost_code_rows(workspace_id, opportunity_id)
        }
        seen_codes: set[str] = set()
        for entry in codes:
            code_value = entry["code"].strip()
            if not code_value:
                raise BaselineError("bad_source")
            row = existing_codes.get(entry.get("id", "")) if entry.get("id") else None
            parent_id = entry.get("parent_id")
            if row is None:
                row = CostCode(
                    workspace_id=wid,
                    opportunity_id=oid,
                    code=code_value,
                    label=entry["label"],
                    variation_category=entry.get("variation_category"),
                    parent_id=uuid.UUID(str(parent_id)) if parent_id else None,
                )
                self.s.add(row)
                self.s.flush()
            else:
                if row.locked_at is not None:
                    raise BaselineError("bad_status")
                row.code = code_value
                row.label = entry["label"]
                row.variation_category = entry.get("variation_category")
                row.parent_id = uuid.UUID(str(parent_id)) if parent_id else None
            seen_codes.add(str(row.id))
        for code_id, row in existing_codes.items():
            if code_id not in seen_codes and row.locked_at is None:
                self.s.delete(row)

        existing_mappings = {
            str(row.id): row for row in self._mapping_rows(workspace_id, opportunity_id)
        }
        seen_mappings: set[str] = set()
        code_ids = {str(row.id) for row in self._cost_code_rows(workspace_id, opportunity_id)}
        for entry in mappings:
            cost_code_id = entry["cost_code_id"]
            if cost_code_id not in code_ids:
                raise BaselineError("not_found")
            row = existing_mappings.get(entry.get("id", "")) if entry.get("id") else None
            if row is None:
                row = CostCodeMapping(
                    workspace_id=wid,
                    opportunity_id=oid,
                    cost_code_id=uuid.UUID(str(cost_code_id)),
                )
                self.s.add(row)
            row.boq_src_row = entry.get("boq_src_row")
            row.finding_id = (
                uuid.UUID(str(entry["finding_id"])) if entry.get("finding_id") else None
            )
            row.description_match = entry.get("description_match")
            self.s.flush()
            seen_mappings.add(str(row.id))
        for mapping_id, row in existing_mappings.items():
            if mapping_id not in seen_mappings:
                self.s.delete(row)
        self.s.commit()
        return self.list_cost_codes(workspace_id, opportunity_id)

    def _lock_cost_codes(self, workspace_id, opportunity_id) -> None:
        locked_at = lock_timestamp()
        for row in self._cost_code_rows(workspace_id, opportunity_id):
            row.locked_at = locked_at
        self.s.commit()

    def compare(self, workspace_id, opportunity_id) -> dict:
        """Award-vs-tender finding delta (spec B5)."""
        return self.compare_award(workspace_id, opportunity_id, findings_only=True)

    def compare_award(self, workspace_id, opportunity_id, *, findings_only: bool = False) -> dict:
        """Full award comparison with clause and BOQ deltas (TS-236)."""
        tender = self.latest(workspace_id, opportunity_id, source="tender")
        award = self.latest(workspace_id, opportunity_id, source="award")
        if tender is None or award is None:
            raise BaselineError("need_two_baselines")

        tender_findings = tender.snapshot.get("findings", [])
        award_findings = award.snapshot.get("findings", [])
        findings_delta = diff_findings(tender_findings, award_findings)
        payload = {
            "baseline_refs": {
                "tender_id": str(tender.id),
                "award_id": str(award.id),
            },
            "tender_version": tender.version,
            "award_version": award.version,
            "findings": findings_delta,
            "added": findings_delta["added"],
            "removed": findings_delta["removed"],
            "changed": findings_delta["changed"],
        }
        if findings_only:
            return payload

        tender_clauses = tender.snapshot.get("clauses") or []
        award_text = self._award_text(workspace_id, opportunity_id)
        award_clauses = self._segment_clause_dicts(award_text) if award_text else []
        payload["clauses"] = diff_clauses(tender_clauses, award_clauses)
        payload["boq"] = diff_boq(tender_findings, award_findings)
        return payload

    def list_watchlist(self, workspace_id, opportunity_id) -> list[dict]:
        rows = list(
            self.s.scalars(
                select(WatchlistControl)
                .where(
                    WatchlistControl.workspace_id == uuid.UUID(str(workspace_id)),
                    WatchlistControl.opportunity_id == uuid.UUID(str(opportunity_id)),
                    WatchlistControl.status == "active",
                )
                .order_by(WatchlistControl.severity.desc(), WatchlistControl.title)
            )
        )
        return [control_dict(r) for r in rows]

    def update_watchlist(
        self,
        workspace_id,
        control_id,
        *,
        owner_user_id=None,
        trigger_text=None,
        review_cadence=None,
        status=None,
        actor_role: str = "estimator",
    ) -> WatchlistControl:
        self._require_approval(workspace_id, role=actor_role, action="watchlist_edit")
        row = self.s.scalar(
            select(WatchlistControl).where(
                WatchlistControl.id == uuid.UUID(str(control_id)),
                WatchlistControl.workspace_id == uuid.UUID(str(workspace_id)),
            )
        )
        if row is None:
            raise BaselineError("not_found")
        if owner_user_id is not None:
            row.owner_user_id = uuid.UUID(str(owner_user_id))
        if trigger_text is not None:
            row.trigger_text = trigger_text
        if review_cadence is not None:
            row.review_cadence = review_cadence
            apply_cadence(row)
        if status is not None:
            if status not in {"active", "closed"}:
                raise BaselineError("bad_status")
            row.status = status
        self.s.commit()
        self.s.refresh(row)
        self._publish(
            "baseline.watchlist_updated",
            {
                "workspace_id": str(workspace_id),
                "opportunity_id": str(row.opportunity_id),
                "control_id": str(row.id),
                "status": row.status,
            },
        )
        return row

    def handover(self, workspace_id, opportunity_id, *, view: str | None = None) -> dict:
        """Commercial handover pack assembled from the latest sealed baseline
        (spec B6 / B16)."""
        latest = self.latest(workspace_id, opportunity_id)
        if latest is None:
            raise BaselineError("no_baseline")
        snap = latest.snapshot
        findings = snap.get("findings", [])
        obligations = [f for f in findings if f.get("severity") in {"critical", "high"}]
        region = snap.get("notice_region")
        notice_rules = self._enrich_notice_rules(
            workspace_id,
            opportunity_id,
            snap.get("notice_rules", []),
            region=region,
        )
        cost_codes = snap.get("cost_codes") or self._cost_code_payload(
            workspace_id, opportunity_id
        )["snapshot"]
        mappings = [m for code in cost_codes for m in code.get("mappings", [])]
        pack = {
            "baseline_id": str(latest.id),
            "version": latest.version,
            "source": latest.source,
            "sealed_hash": latest.content_sha256,
            "sealed_at": latest.sealed_at.isoformat() if latest.sealed_at else None,
            "opportunity": snap.get("opportunity", {}),
            "key_obligations": obligations,
            "notice_register": notice_rules,
            "notice_gaps": snap.get("notice_gaps", []),
            "deadline_calendar": snap.get("deadlines", []),
            "watchlist_controls": self.list_watchlist(workspace_id, opportunity_id),
            "boq_assumptions": boq_assumption_findings(findings),
            "scope_gap_findings": scope_gap_findings(findings),
            "cost_codes": cost_codes,
            "exposure_totals": compute_exposure_totals(findings, mappings),
            "finance_notice_windows": finance_notice_windows(notice_rules),
            "counts": snap.get("counts", {}),
        }
        return filter_handover(pack, view)

    def export_handover(
        self, workspace_id, opportunity_id, fmt: str, *, view: str | None = None
    ) -> tuple[str, str, bytes]:
        """Render the latest sealed handover pack to a file."""
        if self._export_factory is None:
            raise BaselineError("export_unavailable")
        pack = self.handover(workspace_id, opportunity_id, view=view)
        return self._export_factory(self.s).export_handover(
            str(opportunity_id), fmt, pack, view=view or pack.get("view", "full")
        )
