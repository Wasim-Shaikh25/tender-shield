from app.core.module import AppContext, ModuleSpec
from app.modules.billing.plans import PLAN_LIMITS
from app.modules.billing.project_activation import activate_from_webhook, is_project_active
from app.modules.billing.providers import get_provider
from app.modules.billing.router import router
from app.modules.billing.service import BillingService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry

    def express_handler(session, **kwargs):
        fn = reg.get("express.activate_from_webhook")
        return fn(session, **kwargs) if fn else False

    def express_validator(tier, currency, amount_minor):
        fn = reg.get("express.validate_checkout_amount")
        return fn(tier, currency, amount_minor) if fn else True

    def project_handler(session, **kwargs):
        return activate_from_webhook(session, **kwargs)

    def billing_factory(session):
        return BillingService(
            session,
            workspace_factory=reg.get("auth.workspace_factory"),
            express_payment_handler=express_handler,
            express_price_validator=express_validator,
            project_payment_handler=project_handler,
            publish=ctx.events.publish,
        )

    reg.provide("billing.service_factory", billing_factory)

    def _record_usage(session, workspace_id, event, ref_id=None):
        svc = billing_factory(session)
        user_id = svc._user_for_workspace(workspace_id)
        return svc.record_usage(user_id, event, ref_id, workspace_id=workspace_id)

    reg.provide("billing.record_usage", _record_usage)
    reg.provide(
        "billing.seat_limits",
        lambda: {
            plan: limits["seats"]
            for plan, limits in PLAN_LIMITS.items()
            if "seats" in limits
        },
    )
    reg.provide(
        "billing.set_workspace_plan",
        lambda session, workspace_id, new_plan, changed_by, reason=None: billing_factory(
            session
        ).set_workspace_plan(workspace_id, new_plan, changed_by, reason=reason),
    )
    reg.provide(
        "billing.is_project_active",
        lambda session, workspace_id, opportunity_id: is_project_active(
            session, workspace_id, opportunity_id
        ),
    )
    reg.provide("billing.provider_factory", lambda provider: get_provider(ctx.settings, provider))


module = ModuleSpec(
    name="billing",
    version="0.1.0",
    router=router,
    soft_deps=("auth", "express"),
    setup=setup,
)
