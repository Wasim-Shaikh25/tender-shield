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
    def _record_usage(session, workspace_id, event, ref_id=None):
        svc = BillingService(
            session, workspace_factory=reg.get("auth.workspace_factory")
        )
        user_id = svc._user_for_workspace(workspace_id)
        return svc.record_usage(user_id, event, ref_id, workspace_id=workspace_id)

    reg.provide("billing.record_usage", _record_usage)
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
