from app.core.module import AppContext, ModuleSpec
from app.modules.billing.plans import PLAN_LIMITS
from app.modules.billing.providers import get_provider
from app.modules.billing.router import router
from app.modules.billing.service import BillingService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    # Metering consumed by risk/ingestion before starting a review (Doc §7).
    reg.provide(
        "billing.service_factory",
        lambda session: BillingService(
            session, workspace_factory=reg.get("auth.workspace_factory")
        ),
    )
    reg.provide(
        "billing.record_usage",
        lambda session, workspace_id, event, ref_id=None: BillingService(
            session, workspace_factory=reg.get("auth.workspace_factory")
        ).record_usage(workspace_id, event, ref_id),
    )
    # Share plan seat limits with auth so it can enforce plan seat caps.
    reg.provide(
        "billing.seat_limits",
        lambda: {
            plan: limits["seats"]
            for plan, limits in PLAN_LIMITS.items()
            if "seats" in limits
        },
    )
    # Let auth/admin record plan changes in billing's plan_history ledger.
    reg.provide(
        "billing.set_workspace_plan",
        lambda session, workspace_id, new_plan, changed_by, reason=None: BillingService(
            session, workspace_factory=reg.get("auth.workspace_factory")
        ).set_workspace_plan(workspace_id, new_plan, changed_by, reason=reason),
    )
    # Payment-provider adapters are selected by name; live keys are credential-gated.
    reg.provide("billing.provider_factory", lambda provider: get_provider(ctx.settings, provider))


module = ModuleSpec(
    name="billing",
    version="0.1.0",
    router=router,
    soft_deps=("auth",),
    setup=setup,
)
