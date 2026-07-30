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

from app.modules.baseline.models import AwardDocument, Baseline
from app.modules.baseline.notices import extract_notice_rules

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
        loader_provider: Callable[[], object | None] = lambda: None,
        standards_factory: Callable | None = None,
        export_factory: Callable | None = None,
        publish: Callable[[str, dict], object] = lambda event, payload: None,
        pack_id: str = "in-works",
    ):
        self.s = session
        self._findings_factory = findings_factory
        self._review_factory = review_factory
        self._ingestion_factory = ingestion_factory
        self._loader_provider = loader_provider
        self._standards_factory = standards_factory
        self._export_factory = export_factory
        self._publish = publish
        self._pack_id = pack_id

    # ---- reads from other modules (capabilities only) ---------------------
    def _accepted_findings(self, workspace_id, opportunity_id) -> list[dict]:
        if self._findings_factory is None:
            raise BaselineError("findings_unavailable")
        rows = self._findings_factory(self.s).list(workspace_id, opportunity_id)
        return [
            {
                "category": r.category,
                "severity": r.severity,
                "title": r.title,
                "detail": r.detail,
                "source_page": r.source_page,
                "source_quote": r.source_quote,
                "suggested_action": r.suggested_action,
                "amount_exposure": r.amount_exposure,
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
        meta = self._opportunity_meta(workspace_id, opportunity_id)
        analysis = self._notice_analysis(
            workspace_id, opportunity_id, findings, meta.get("jurisdiction")
        )
        snapshot = {
            "source": source,
            "opportunity": meta,
            "findings": findings,
            "deadlines": deadlines,
            "notice_rules": analysis["rules"],
            "notice_gaps": analysis["gaps"],
            "notice_region": analysis["region"],
            "counts": {
                "findings": len(findings),
                "deadlines": len(deadlines),
                "notice_rules": len(analysis["rules"]),
                "notice_gaps": len(analysis["gaps"]),
            },
        }
        if source == "award":
            snapshot["award_text_preview"] = award_text[:500]
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
                "opportunity_id": str(opp),
                "baseline_id": str(row.id),
                "version": row.version,
                "source": source,
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
            return {
                "source": "baseline",
                "version": latest.version,
                "region": snap.get("notice_region"),
                "rules": snap.get("notice_rules", []),
                "gaps": snap.get("notice_gaps", []),
            }
        findings = self._accepted_findings(workspace_id, opportunity_id)
        meta = self._opportunity_meta(workspace_id, opportunity_id)
        analysis = self._notice_analysis(
            workspace_id, opportunity_id, findings, meta.get("jurisdiction")
        )
        return {
            "source": "live",
            "version": None,
            "region": analysis["region"],
            "rules": analysis["rules"],
            "gaps": analysis["gaps"],
        }

    @staticmethod
    def _by_identity(findings: list[dict]) -> dict[tuple[str, str], dict]:
        return {(f.get("category", ""), f.get("title", "")): f for f in findings}

    def compare(self, workspace_id, opportunity_id) -> dict:
        """Award-vs-tender delta: latest tender seal vs latest award seal
        (spec B5). Deterministic diff by finding identity (category+title)."""
        tender = self.latest(workspace_id, opportunity_id, source="tender")
        award = self.latest(workspace_id, opportunity_id, source="award")
        if tender is None or award is None:
            raise BaselineError("need_two_baselines")
        t = self._by_identity(tender.snapshot.get("findings", []))
        a = self._by_identity(award.snapshot.get("findings", []))
        added = [a[k] for k in a.keys() - t.keys()]
        removed = [t[k] for k in t.keys() - a.keys()]
        changed = []
        for k in t.keys() & a.keys():
            tf, af = t[k], a[k]
            diffs = {
                field: {"tender": tf.get(field), "award": af.get(field)}
                for field in ("severity", "detail", "amount_exposure")
                if tf.get(field) != af.get(field)
            }
            if diffs:
                changed.append({"category": k[0], "title": k[1], "changes": diffs})
        return {
            "tender_version": tender.version,
            "award_version": award.version,
            "added": added,
            "removed": removed,
            "changed": changed,
        }

    def handover(self, workspace_id, opportunity_id) -> dict:
        """Commercial handover pack assembled from the latest sealed baseline
        (spec B6)."""
        latest = self.latest(workspace_id, opportunity_id)
        if latest is None:
            raise BaselineError("no_baseline")
        snap = latest.snapshot
        findings = snap.get("findings", [])
        obligations = [f for f in findings if f.get("severity") in {"critical", "high"}]
        return {
            "baseline_id": str(latest.id),
            "version": latest.version,
            "source": latest.source,
            "sealed_hash": latest.content_sha256,
            "sealed_at": latest.sealed_at.isoformat() if latest.sealed_at else None,
            "opportunity": snap.get("opportunity", {}),
            "key_obligations": obligations,
            "notice_register": snap.get("notice_rules", []),
            "notice_gaps": snap.get("notice_gaps", []),
            "deadline_calendar": snap.get("deadlines", []),
            "counts": snap.get("counts", {}),
        }

    def export_handover(self, workspace_id, opportunity_id, fmt: str) -> tuple[str, str, bytes]:
        """Render the latest sealed handover pack to a file."""
        if self._export_factory is None:
            raise BaselineError("export_unavailable")
        pack = self.handover(workspace_id, opportunity_id)
        return self._export_factory(self.s).export_handover(str(opportunity_id), fmt, pack)
