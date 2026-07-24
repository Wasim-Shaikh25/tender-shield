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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.baseline.models import Baseline
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
        publish: Callable[[str, dict], object] = lambda event, payload: None,
    ):
        self.s = session
        self._findings_factory = findings_factory
        self._review_factory = review_factory
        self._ingestion_factory = ingestion_factory
        self._publish = publish

    # ---- reads from other modules (capabilities only) ---------------------
    def _accepted_findings(self, org_id, opportunity_id) -> list[dict]:
        if self._findings_factory is None:
            raise BaselineError("findings_unavailable")
        rows = self._findings_factory(self.s).list(org_id, opportunity_id)
        return [
            {
                "category": r.category,
                "severity": r.severity,
                "title": r.title,
                "detail": r.detail,
                "source_page": r.source_page,
                "source_quote": r.source_quote,
                "suggested_action": r.suggested_action,
                "amount_exposure": (
                    float(r.amount_exposure) if r.amount_exposure is not None else None
                ),
                "review_status": r.review_status,
            }
            for r in rows
            if r.review_status in _ACCEPTED
        ]

    def _confirmed_deadlines(self, org_id, opportunity_id) -> list[dict]:
        if self._ingestion_factory is None:
            return []
        svc = self._ingestion_factory(self.s)
        out = []
        for d in svc.list_deadlines(org_id, opportunity_id):
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

    def _clause_records(self, org_id, opportunity_id) -> list[dict]:
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
        for c in lister(org_id, opportunity_id):
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

    def _notice_rules(self, org_id, opportunity_id, findings: list[dict]) -> list[dict]:
        records = findings + self._clause_records(org_id, opportunity_id)
        return [r.as_dict() for r in extract_notice_rules(records)]

    def _opportunity_meta(self, org_id, opportunity_id) -> dict:
        if self._ingestion_factory is None:
            return {"id": str(opportunity_id), "title": "this tender"}
        opp = self._ingestion_factory(self.s).get_opportunity(org_id, opportunity_id)
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

    def _gate_ok(self, org_id, opportunity_id) -> None:
        """Freeze is blocked until review completes (spec B1, Doc §11.4)."""
        if self._review_factory is None:
            raise BaselineError("review_unavailable")
        gate = self._review_factory(self.s).gate(org_id, opportunity_id)
        if not gate.get("export_allowed", False):
            raise BaselineError("review_incomplete")

    # ---- snapshot + hashing ----------------------------------------------
    def _build_snapshot(self, org_id, opportunity_id, source: str) -> dict:
        findings = self._accepted_findings(org_id, opportunity_id)
        deadlines = self._confirmed_deadlines(org_id, opportunity_id)
        notice_rules = self._notice_rules(org_id, opportunity_id, findings)
        return {
            "source": source,
            "opportunity": self._opportunity_meta(org_id, opportunity_id),
            "findings": findings,
            "deadlines": deadlines,
            "notice_rules": notice_rules,
            "counts": {
                "findings": len(findings),
                "deadlines": len(deadlines),
                "notice_rules": len(notice_rules),
            },
        }

    @staticmethod
    def _hash(snapshot: dict) -> str:
        """SHA-256 over the canonical snapshot (excludes volatile sealed_at,
        which is not part of the snapshot dict) — the seal (spec B3)."""
        canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # ---- freeze / read ----------------------------------------------------
    def freeze(self, org_id, opportunity_id, *, source="tender", note=None, sealer_id=None):
        if source not in {"tender", "award"}:
            raise BaselineError("bad_source")
        self._gate_ok(org_id, opportunity_id)
        snapshot = self._build_snapshot(org_id, opportunity_id, source)
        opp = uuid.UUID(str(opportunity_id))
        next_version = (
            self.s.scalar(
                select(func.coalesce(func.max(Baseline.version), 0)).where(
                    Baseline.opportunity_id == opp
                )
            )
            + 1
        )
        row = Baseline(
            org_id=uuid.UUID(str(org_id)),
            opportunity_id=opp,
            version=next_version,
            source=source,
            content_sha256=self._hash(snapshot),
            snapshot=snapshot,
            note=note,
            sealed_by=uuid.UUID(str(sealer_id)) if sealer_id else None,
        )
        self.s.add(row)
        self.s.commit()
        # Audit the seal through the review module's append-only log if present.
        if self._review_factory is not None:
            self._review_factory(self.s).audit(
                org_id,
                actor=sealer_id,
                action="baseline.sealed",
                object_type="baseline",
                object_id=row.id,
                detail={"version": next_version, "source": source, "hash": row.content_sha256},
            )
        self._publish(
            "baseline.sealed",
            {
                "opportunity_id": str(opp),
                "baseline_id": str(row.id),
                "version": next_version,
                "source": source,
            },
        )
        return row

    def list(self, org_id, opportunity_id) -> list[Baseline]:
        return list(
            self.s.scalars(
                select(Baseline)
                .where(
                    Baseline.org_id == uuid.UUID(str(org_id)),
                    Baseline.opportunity_id == uuid.UUID(str(opportunity_id)),
                )
                .order_by(Baseline.version.desc())
            )
        )

    def get(self, org_id, baseline_id) -> Baseline | None:
        return self.s.scalar(
            select(Baseline).where(
                Baseline.id == uuid.UUID(str(baseline_id)),
                Baseline.org_id == uuid.UUID(str(org_id)),
            )
        )

    def latest(self, org_id, opportunity_id, *, source: str | None = None) -> Baseline | None:
        stmt = select(Baseline).where(
            Baseline.org_id == uuid.UUID(str(org_id)),
            Baseline.opportunity_id == uuid.UUID(str(opportunity_id)),
        )
        if source is not None:
            stmt = stmt.where(Baseline.source == source)
        return self.s.scalar(stmt.order_by(Baseline.version.desc()))

    def verify(self, org_id, baseline_id) -> dict:
        row = self.get(org_id, baseline_id)
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
    def notice_register(self, org_id, opportunity_id) -> dict:
        """The notice-rule register from the latest sealed baseline; falls back
        to the live accepted findings when nothing is sealed yet."""
        latest = self.latest(org_id, opportunity_id)
        if latest is not None:
            rules = latest.snapshot.get("notice_rules", [])
            return {"source": "baseline", "version": latest.version, "rules": rules}
        findings = self._accepted_findings(org_id, opportunity_id)
        rules = self._notice_rules(org_id, opportunity_id, findings)
        return {"source": "live", "version": None, "rules": rules}

    @staticmethod
    def _by_identity(findings: list[dict]) -> dict[tuple[str, str], dict]:
        return {(f.get("category", ""), f.get("title", "")): f for f in findings}

    def compare(self, org_id, opportunity_id) -> dict:
        """Award-vs-tender delta: latest tender seal vs latest award seal
        (spec B5). Deterministic diff by finding identity (category+title)."""
        tender = self.latest(org_id, opportunity_id, source="tender")
        award = self.latest(org_id, opportunity_id, source="award")
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

    def handover(self, org_id, opportunity_id) -> dict:
        """Commercial handover pack assembled from the latest sealed baseline
        (spec B6)."""
        latest = self.latest(org_id, opportunity_id)
        if latest is None:
            raise BaselineError("no_baseline")
        snap = latest.snapshot
        findings = snap.get("findings", [])
        obligations = [
            f for f in findings if f.get("severity") in {"critical", "high"}
        ]
        return {
            "baseline_id": str(latest.id),
            "version": latest.version,
            "source": latest.source,
            "sealed_hash": latest.content_sha256,
            "sealed_at": latest.sealed_at.isoformat() if latest.sealed_at else None,
            "opportunity": snap.get("opportunity", {}),
            "key_obligations": obligations,
            "notice_register": snap.get("notice_rules", []),
            "deadline_calendar": snap.get("deadlines", []),
            "counts": snap.get("counts", {}),
        }
