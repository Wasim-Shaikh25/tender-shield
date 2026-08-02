"""`outcomes` module registration (TS-215, spec §Public interface)."""

from app.core.module import AppContext, ModuleSpec
from app.modules.outcomes.router import router
from app.modules.outcomes.service import OutcomesService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry

    def factory(session):
        return OutcomesService(
            session,
            findings_factory=reg.get("findings.store_factory"),
            comparable_awards=reg.get("marketdata.comparable_awards"),
            award_prefill=reg.get("marketdata.award_prefill"),
            publish=ctx.events.publish,
        )

    reg.provide("outcomes.service_factory", factory)
    reg.provide(
        "outcomes.for_opportunity",
        lambda session, workspace_id, opportunity_id: factory(session).for_opportunity(
            workspace_id, opportunity_id
        ),
    )
    reg.provide(
        "outcomes.margin_protected",
        lambda session, workspace_id, currency="INR": factory(session).margin_protected(
            workspace_id, currency=currency
        ),
    )
    reg.provide(
        "outcomes.bid_outcomes_for_workspace",
        lambda session, workspace_id: factory(session).bid_outcomes_for_workspace(workspace_id),
    )
    reg.provide(
        "outcomes.risk_materializations_for_workspace",
        lambda session, workspace_id: factory(session).risk_materializations_for_workspace(
            workspace_id
        ),
    )
    reg.provide(
        "outcomes.claim_recoveries_for_workspace",
        lambda session, workspace_id: factory(session).claim_recoveries_for_workspace(
            workspace_id
        ),
    )


module = ModuleSpec(
    name="outcomes",
    version="0.1.0",
    router=router,
    soft_deps=("findings", "marketdata", "auth"),
    setup=setup,
)
