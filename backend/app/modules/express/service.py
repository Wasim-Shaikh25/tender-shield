"""Express lane service (TS-208/209/210)."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.express.models import ExDocument, ExPurchase, ExSession
from app.modules.express.prices import currency_for_country, tier_price_minor
from app.modules.express.report import build_report
from app.modules.express.teaser import build_teaser

DEFAULT_TTL_HOURS = 72
EXPRESS_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ACKNOWLEDGMENT_VERSION = "express-unreviewed-v1"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class ExpressError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ExpressService:
    def __init__(
        self,
        session: Session,
        *,
        create_workspace: Callable | None = None,
        ingestion_factory: Callable | None = None,
        findings_factory: Callable | None = None,
        run_risk: Callable | None = None,
        provider_factory: Callable | None = None,
        publish: Callable[[str, dict], int] | None = None,
    ):
        self.s = session
        self._create_workspace = create_workspace
        self._ingestion_factory = ingestion_factory
        self._findings_factory = findings_factory
        self._run_risk = run_risk
        self._provider_factory = provider_factory
        self._publish = publish

    def create_session(
        self,
        *,
        email: str,
        tier: str = "snapshot",
        acknowledgment: dict | None = None,
        acknowledgment_version: str = ACKNOWLEDGMENT_VERSION,
        client_ip: str | None = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> ExSession:
        if not acknowledgment or not acknowledgment.get("accepted"):
            raise ExpressError("acknowledgment_required")
        if self._create_workspace is None:
            raise ExpressError("workspace_unavailable")
        workspace_id = self._create_workspace(self.s, label="express")
        row = ExSession(
            workspace_id=workspace_id,
            token=secrets.token_urlsafe(32),
            email=email.strip().lower(),
            tier=tier,
            state="created",
            acknowledgment=acknowledgment,
            acknowledgment_version=acknowledgment_version,
            client_ip=client_ip,
            expires_at=_utc_now() + timedelta(hours=ttl_hours),
        )
        if self._ingestion_factory is not None:
            opp = self._ingestion_factory(self.s).create_opportunity(
                workspace_id,
                title=f"Express session {row.email}",
            )
            row.opportunity_id = opp.id
        self.s.add(row)
        self.s.commit()
        self.s.refresh(row)
        return row

    def get_by_token(self, token: str) -> ExSession | None:
        row = self.s.scalar(select(ExSession).where(ExSession.token == token))
        if row is None:
            return None
        if row.expires_at and _as_utc(row.expires_at) < _utc_now():
            row.state = "expired"
            self.s.commit()
            return None
        return row

    def require_session(self, token: str) -> ExSession:
        row = self.get_by_token(token)
        if row is None:
            raise ExpressError("session_not_found")
        return row

    def upload_document(
        self,
        token: str,
        *,
        filename: str,
        data: bytes,
        retention_days: int = 90,
    ) -> ExDocument:
        if len(data) > EXPRESS_MAX_UPLOAD_BYTES:
            raise ExpressError("upload_too_large")
        session = self.require_session(token)
        digest = hashlib.sha256(data).hexdigest()
        doc = ExDocument(
            workspace_id=session.workspace_id,
            session_id=session.id,
            filename=filename,
            sha256=digest,
            retention_until=_utc_now() + timedelta(days=retention_days),
        )
        session.state = "uploaded"
        self.s.add(doc)
        self.s.commit()
        self.s.refresh(doc)

        if self._ingestion_factory is not None and session.opportunity_id is not None:
            ingestion = self._ingestion_factory(self.s)
            text = ingestion.extract_text(filename, data)
            ingestion.register_document(
                session.workspace_id,
                session.opportunity_id,
                filename,
                sample_text=text,
                sha256=digest,
            )
            if self._run_risk is not None:
                self._run_risk(self.s, session.workspace_id, session.opportunity_id)
        return doc

    def render_teaser(self, token: str) -> dict:
        session = self.require_session(token)
        if session.opportunity_id is None or self._ingestion_factory is None:
            raise ExpressError("teaser_unavailable")

        ingestion = self._ingestion_factory(self.s)
        opp_id = str(session.opportunity_id)
        deadlines = [
            {
                "kind": d.kind,
                "due_at": d.due_at.isoformat() if d.due_at else None,
                "description": d.description,
                "source_page": d.source_page,
                "source_quote": d.source_quote,
                "confirmed": d.confirmed,
            }
            for d in ingestion.list_deadlines(session.workspace_id, opp_id)
        ]
        missing_docs = ingestion.missing_doc_report(session.workspace_id, opp_id)

        findings: list[dict] = []
        if self._findings_factory is not None:
            store = self._findings_factory(self.s)
            findings = [
                {
                    "producer": row.producer,
                    "kind": row.kind,
                    "category": row.category,
                    "severity": row.severity,
                    "title": row.title,
                    "source_page": row.source_page,
                    "source_quote": row.source_quote,
                    "amount_exposure": row.amount_exposure,
                }
                for row in store.list(session.workspace_id, opp_id)
            ]

        teaser = build_teaser(
            deadlines=deadlines,
            missing_docs=missing_docs,
            findings=findings,
        )
        session.state = "teaser_ready"
        self.s.commit()
        if self._publish:
            self._publish(
                "express.teaser_ready",
                {
                    "token": token,
                    "workspace_id": str(session.workspace_id),
                    "opportunity_id": opp_id,
                },
            )
        return {
            "token": token,
            "tier": session.tier,
            "state": session.state,
            "teaser": teaser,
        }

    def create_checkout(
        self,
        token: str,
        *,
        country: str = "IN",
        amount_minor: int | None = None,
    ) -> dict:
        session = self.require_session(token)
        if session.state not in {"uploaded", "teaser_ready", "checkout_pending"}:
            raise ExpressError("checkout_unavailable")
        currency = currency_for_country(country)
        try:
            expected = tier_price_minor(session.tier, country=country)
        except ValueError as exc:
            raise ExpressError("unknown_tier") from exc
        if amount_minor is not None and amount_minor != expected:
            raise ExpressError("amount_mismatch")
        if self._provider_factory is None:
            raise ExpressError("billing_unavailable")

        provider_name = "razorpay" if country.upper() == "IN" else "stripe"
        notes = {
            "kind": "express",
            "express_session_id": str(session.id),
            "express_token": token,
            "tier": session.tier,
            "workspace_id": str(session.workspace_id),
            "amount_minor": expected,
            "currency": currency,
        }
        if session.opportunity_id:
            notes["opportunity_id"] = str(session.opportunity_id)

        provider = self._provider_factory(provider_name)
        if provider_name == "stripe":
            checkout = provider.create_session(expected, currency.lower(), notes)
            order_id = checkout.get("session_id", "")
        else:
            checkout = provider.create_order(expected, currency, notes)
            order_id = checkout.get("order_id", "")

        purchase = self.s.scalar(
            select(ExPurchase).where(
                ExPurchase.session_id == session.id,
                ExPurchase.provider == provider_name,
                ExPurchase.provider_order_id == order_id,
            )
        )
        if purchase is None:
            purchase = ExPurchase(
                workspace_id=session.workspace_id,
                session_id=session.id,
                provider=provider_name,
                provider_order_id=order_id,
                amount_minor=expected,
                currency=currency,
            )
            self.s.add(purchase)
        session.state = "checkout_pending"
        self.s.commit()
        return {
            "token": token,
            "tier": session.tier,
            "amount_minor": expected,
            "currency": currency,
            "provider": provider_name,
            "checkout": checkout,
            "note": "activation happens via the signed webhook, never this response",
        }

    def is_activated(self, token: str) -> bool:
        session = self.require_session(token)
        purchase = self.s.scalar(
            select(ExPurchase).where(
                ExPurchase.session_id == session.id,
                ExPurchase.activated_at.is_not(None),
            )
        )
        return purchase is not None

    def get_report(self, token: str) -> dict:
        session = self.require_session(token)
        if not self.is_activated(token):
            raise ExpressError("report_locked")
        if session.opportunity_id is None or self._ingestion_factory is None:
            raise ExpressError("report_unavailable")

        ingestion = self._ingestion_factory(self.s)
        opp_id = str(session.opportunity_id)
        deadlines = [
            {
                "kind": d.kind,
                "due_at": d.due_at.isoformat() if d.due_at else None,
                "description": d.description,
                "source_page": d.source_page,
                "source_quote": d.source_quote,
                "confirmed": d.confirmed,
            }
            for d in ingestion.list_deadlines(session.workspace_id, opp_id)
        ]
        missing_docs = ingestion.missing_doc_report(session.workspace_id, opp_id)
        findings: list[dict] = []
        if self._findings_factory is not None:
            store = self._findings_factory(self.s)
            findings = [
                {
                    "producer": row.producer,
                    "kind": row.kind,
                    "category": row.category,
                    "severity": row.severity,
                    "title": row.title,
                    "detail": row.detail,
                    "source_page": row.source_page,
                    "source_quote": row.source_quote,
                    "amount_exposure": row.amount_exposure,
                    "currency": row.currency,
                }
                for row in store.list(session.workspace_id, opp_id)
            ]
        report = build_report(
            deadlines=deadlines,
            missing_docs=missing_docs,
            findings=findings,
            tier=session.tier,
        )
        return {
            "token": token,
            "tier": session.tier,
            "state": session.state,
            "report": report,
        }
