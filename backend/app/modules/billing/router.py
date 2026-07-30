from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import audit as audit_log
from app.core.deps import get_session, require
from app.core.pagination import PaginationParams, paginated_list_response
from app.core.ratelimit import RateLimitDep
from app.modules.billing.plans import PAYGO_PRICE_INR_PAISE, SUBSCRIPTION_PRICES, PaywallError
from app.modules.billing.providers import BillingError
from app.modules.billing.service import BillingService

router = APIRouter()


def _service(request: Request, session: Session) -> BillingService:
    reg = request.app.state.ctx.registry
    return BillingService(session, workspace_factory=reg.get("auth.workspace_factory"))


COUNTRY_CURRENCY: dict[str, str] = {
    "IN": "inr",
    "AE": "aed",
    "SA": "sar",
    "QA": "qar",
    "GB": "gbp",
}
DEFAULT_COUNTRY = "IN"


def _currency_for_country(country: str | None) -> str:
    return COUNTRY_CURRENCY.get((country or DEFAULT_COUNTRY).upper(), "inr")


class CheckoutBody(BaseModel):
    provider: str | None = None  # razorpay | stripe; defaults by country
    kind: str  # paygo | subscription
    plan: str | None = None
    opportunity_id: str | None = None
    amount_minor: int | None = None


class BillingSettingsBody(BaseModel):
    gstin: str | None = None
    pan: str | None = None
    billing_address: str | None = None
    state: str | None = None
    payment_method_id: str | None = None


@router.get("/status")
def status(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
):
    return _service(request, session).status(principal.workspace_id)


@router.post("/checkout", dependencies=[Depends(RateLimitDep(10, 60))])
def checkout(
    body: CheckoutBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    """Creates a provider order/subscription handle for the client SDK.
    Activates NOTHING — only the verified webhook does (Doc §15.1)."""
    if not (principal.is_superadmin or principal.email_verified):
        raise HTTPException(403, "email_not_verified")

    svc = _service(request, session)
    workspace = svc._workspaces().get(principal.workspace_id)
    country = getattr(workspace, "country", None) or DEFAULT_COUNTRY
    currency = _currency_for_country(country)

    if body.kind == "paygo":
        expected = PAYGO_PRICE_INR_PAISE
    elif body.kind == "subscription":
        expected = SUBSCRIPTION_PRICES.get(currency, {}).get(body.plan or "")
        if not expected:
            raise HTTPException(400, "unknown_subscription_plan")
    else:
        raise HTTPException(400, "unknown_checkout_kind")

    if body.amount_minor is not None and body.amount_minor != expected:
        raise HTTPException(400, "amount_mismatch")
    amount = expected

    notes = {"workspace_id": str(principal.workspace_id), "kind": body.kind}
    if body.opportunity_id:
        notes["opportunity_id"] = body.opportunity_id
    if body.plan:
        notes["plan"] = body.plan

    chosen_provider = body.provider
    if not chosen_provider:
        # India defaults to Razorpay; all other supported countries default to Stripe.
        chosen_provider = "razorpay" if country.upper() == "IN" else "stripe"

    try:
        provider = request.app.state.ctx.registry.get("billing.provider_factory")(chosen_provider)
        if chosen_provider == "stripe":
            result = provider.create_session(amount, currency, notes)
        else:
            result = provider.create_order(amount, currency, notes)
    except BillingError as exc:
        raise HTTPException(
            503, detail={"code": str(exc), "message": "payment_provider_unavailable"}
        ) from exc

    result["note"] = "activation happens via the signed webhook, never this response"
    audit_log.log(
        request,
        session,
        workspace_id=principal.workspace_id,
        actor_user_id=principal.user_id,
        action="billing.checkout",
        object_type="workspace",
        object_id=principal.workspace_id,
        detail={
            "provider": chosen_provider,
            "kind": body.kind,
            "plan": body.plan,
            "amount_minor": amount,
            "currency": currency,
        },
    )
    return result


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
    response: Response,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("viewer")),
    page: PaginationParams = Depends(),
):
    items = [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "amount_minor": inv.amount_minor,
            "currency": inv.currency,
            "status": inv.status,
            "provider": inv.provider,
            "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
            "created_at": inv.created_at.isoformat(),
        }
        for inv in _service(request, session).list_invoices(principal.workspace_id)
    ]
    return {"invoices": paginated_list_response(items, page, response)}


@router.get("/settings")
def get_billing_settings(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    return _service(request, session).get_billing_settings(principal.workspace_id)


@router.put("/settings")
def update_billing_settings(
    body: BillingSettingsBody,
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        settings = _service(request, session).update_billing_settings(
            principal.workspace_id, body.model_dump(exclude_none=True)
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except PaywallError as exc:
        raise HTTPException(402, exc.code) from exc
    audit_log.log(
        request,
        session,
        workspace_id=principal.workspace_id,
        actor_user_id=principal.user_id,
        action="billing.settings_updated",
        object_type="workspace",
        object_id=principal.workspace_id,
        detail=settings,
    )
    return settings


@router.post("/cancel")
def cancel_subscription(
    request: Request,
    session: Session = Depends(get_session),
    principal: Any = Depends(require("admin")),
):
    try:
        result = _service(request, session).cancel_subscription(
            principal.workspace_id, principal.user_id
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except PaywallError as exc:
        raise HTTPException(402, exc.code) from exc
    audit_log.log(
        request,
        session,
        workspace_id=principal.workspace_id,
        actor_user_id=principal.user_id,
        action="billing.subscription_cancelled",
        object_type="workspace",
        object_id=principal.workspace_id,
        detail={"previous_plan": result.get("previous_plan")},
    )
    return result


@router.post("/webhooks/razorpay", dependencies=[Depends(RateLimitDep(50, 60))])
async def razorpay_webhook(request: Request, session: Session = Depends(get_session)):
    raw = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    secret = request.app.state.ctx.settings.razorpay_webhook_secret
    result = _service(request, session).process_razorpay_webhook(raw, sig, secret)
    if not result.get("ok"):
        raise HTTPException(400, result.get("reason", "webhook_failed"))
    if result.get("workspace_id"):
        audit_log.log(
            request,
            session,
            workspace_id=result["workspace_id"],
            actor_user_id=None,
            action="billing.payment_received",
            object_type="workspace",
            object_id=result["workspace_id"],
            detail={"provider": "razorpay", "applied": result.get("applied")},
        )
    return result


@router.post("/webhooks/stripe", dependencies=[Depends(RateLimitDep(50, 60))])
async def stripe_webhook(request: Request, session: Session = Depends(get_session)):
    raw = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    secret = request.app.state.ctx.settings.stripe_webhook_secret
    result = _service(request, session).process_stripe_webhook(raw, sig, secret)
    if not result.get("ok"):
        raise HTTPException(400, result.get("reason", "webhook_failed"))
    if result.get("workspace_id"):
        audit_log.log(
            request,
            session,
            workspace_id=result["workspace_id"],
            actor_user_id=None,
            action="billing.payment_received",
            object_type="workspace",
            object_id=result["workspace_id"],
            detail={"provider": "stripe", "applied": result.get("applied")},
        )
    return result
