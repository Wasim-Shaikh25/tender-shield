from app.core.module import AppContext, ModuleSpec
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
    # Consumed by export to decide the free-tier watermark (Doc §7, R-004 §B) —
    # export must not import billing (CLAUDE.md §2).
    reg.provide(
        "billing.export_entitlement",
        lambda session, workspace_id: BillingService(
            session, workspace_factory=reg.get("auth.workspace_factory")
        ).export_entitlement(workspace_id),
    )
    # Consumed by auth's seat check (R-009 §B.3) — seats_used is supplied by
    # the CALLER (auth) because billing may not query auth's own
    # workspace_members/invitations tables (CLAUDE.md §2).
    reg.provide(
        "billing.entitlements",
        lambda session, workspace_id, seats_used=0: BillingService(
            session, workspace_factory=reg.get("auth.workspace_factory")
        ).entitlements(workspace_id, seats_used=seats_used),
    )
    # Consumed by auth.signup (R-006 §B.7) — auth does the self-referral
    # domain check itself (it owns User/Workspace) and only calls this to
    # record the relationship; billing owns the Referral/Credit tables.
    reg.provide(
        "billing.record_referral_signup",
        lambda session, referrer_workspace_id, referred_workspace_id, code: BillingService(
            session, workspace_factory=reg.get("auth.workspace_factory")
        ).record_referral_signup(referrer_workspace_id, referred_workspace_id, code),
    )
    # Consumed by auth.signup (R-006 §B.7) — resolves a referral code through
    # billing's own non-RLS `referral_codes` table, since the referred user
    # isn't a member of any workspace yet and RLS would hide a `workspaces`
    # query for the referrer (see referral_codes' docstring in models.py).
    reg.provide(
        "billing.resolve_referral_code",
        lambda session, code: BillingService(
            session, workspace_factory=reg.get("auth.workspace_factory")
        ).resolve_referral_code(code),
    )


module = ModuleSpec(
    name="billing",
    version="0.1.0",
    router=router,
    soft_deps=("auth",),
    setup=setup,
)
