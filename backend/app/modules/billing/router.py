from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_session, require
from app.modules.billing.plans import PaywallError
from app.modules.billing.providers.select import select_provider
from app.modules.billing.service import BillingService

router = APIRouter()


def _service(request: Request, session: Session) -> BillingService:
    reg = request.app.state.ctx.registry
    settings = request.app.state.ctx.settings
    return BillingService(
        session,
        workspace_factory=reg.get("auth.workspace_factory"),
        provider_factory=lambda country: select_provider(settings, country),
        settings=settings,
    )


class CheckoutBody(BaseModel):
    kind: str  # paygo | subscription
    plan: str | None = None
    opportunity_id: str | None = None


class BillingDetailsBody(BaseModel):
    legal_name: str | None = None
    gstin: str | None = None
    billing_address: dict = {}
    place_of_supply: str | None = None


@router.get("/status")
def status(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).status(principal.workspace_id)


@router.post("/checkout")
def checkout(
    body: CheckoutBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    """Creates a real payment_intents row + provider order (Doc §15.1,
    R-005 §B). Activates NOTHING — only the verified webhook does. Plan and
    price are resolved server-side; client input selects which plan, never
    what it costs."""
    if body.kind not in ("paygo", "subscription"):
        raise HTTPException(400, "bad_kind")
    if body.kind == "paygo" and not body.opportunity_id:
        # A paygo payment is scoped to the one opportunity it unlocks
        # (BillingService._has_paid_review checks it by ref_id) — without an
        # opportunity_id there'd be nothing for authorize_review to match the
        # payment against.
        raise HTTPException(400, "opportunity_id_required")
    plan = "paygo" if body.kind == "paygo" else (body.plan or "")
    try:
        return _service(request, session).create_checkout(
            principal.workspace_id,
            kind=body.kind,
            plan=plan,
            opportunity_id=body.opportunity_id,
        )
    except PaywallError as exc:
        status_code = 503 if exc.code == "payment_provider_unavailable" else 400
        raise HTTPException(status_code, exc.code) from exc


@router.get("/intents/{intent_id}")
def intent_status(
    intent_id: str,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    """Polled by the client after opening the provider checkout (R-008 §4) —
    the client-side handler activates nothing; this just reports what the
    webhook has (or hasn't) confirmed yet."""
    return _service(request, session).get_intent_status(principal.workspace_id, intent_id)


@router.post("/authorize-review")
def authorize_review(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("estimator")),
):
    try:
        grant = _service(request, session).authorize_review(principal.workspace_id)
    except PaywallError as exc:
        raise HTTPException(402, detail={"code": exc.code, "upsell": exc.upsell}) from exc
    return {
        "kind": grant.kind,
        "watermark": grant.watermark,
        "requires_payment": grant.requires_payment,
    }


@router.get("/invoices")
def list_invoices(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return {
        "invoices": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "doc_type": inv.doc_type,
                "base_minor": inv.base_minor,
                "cgst_minor": inv.cgst_minor,
                "sgst_minor": inv.sgst_minor,
                "igst_minor": inv.igst_minor,
                "round_off_minor": inv.round_off_minor,
                "amount_minor": inv.total_minor,
                "currency": inv.currency,
                "status": inv.status,
                "provider": inv.provider,
                "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
                "created_at": inv.created_at.isoformat(),
            }
            for inv in _service(request, session).list_invoices(principal.workspace_id)
        ]
    }


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(
    invoice_id: int,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    """Served through an authorized, workspace-scoped route — never a public
    URL (R-007 §B.8); a member of another workspace gets 404 (R-007 §A9)."""
    pdf = _service(request, session).get_invoice_pdf(principal.workspace_id, invoice_id)
    if pdf is None:
        raise HTTPException(404, "invoice_not_found")
    return Response(content=pdf, media_type="application/pdf")


@router.put("/details")
def set_billing_details(
    body: BillingDetailsBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    """Buyer GST identity (R-007 §B.1) — must be set before a paid checkout
    for an Indian workspace, since it cannot be added to an already-issued
    invoice retroactively."""
    try:
        _service(request, session).set_billing_details(
            principal.workspace_id,
            legal_name=body.legal_name,
            gstin=body.gstin,
            billing_address=body.billing_address,
            place_of_supply=body.place_of_supply,
        )
    except PaywallError as exc:
        raise HTTPException(400, exc.code) from exc
    return {"ok": True}


@router.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, session: Session = Depends(get_session)):
    raw = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    result = _service(request, session).process_webhook(raw, sig)
    if not result.get("ok"):
        raise HTTPException(400, result.get("reason", "webhook_failed"))
    return result
