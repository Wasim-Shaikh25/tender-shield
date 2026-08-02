from app.core.module import AppContext, ModuleSpec
from app.modules.controltower.router import router
from app.modules.controltower.service import ControlTowerService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry

    def factory(session):
        return ControlTowerService(
            session,
            ingestion_factory=reg.get("ingestion.service_factory"),
            claims_factory=reg.get("claims.service_factory"),
            change_factory=reg.get("change.service_factory"),
            evidence_factory=reg.get("evidence.service_factory"),
            findings_factory=reg.get("findings.store_factory"),
            outcomes_factory=reg.get("outcomes.service_factory"),
            billing_factory=reg.get("billing.service_factory"),
            publish=ctx.events.publish,
        )

    reg.provide("controltower.service_factory", factory)
    reg.provide(
        "controltower.exposure_for_opportunity",
        lambda session, workspace_id, opportunity_id, **kw: factory(
            session
        ).exposure_for_opportunity(workspace_id, opportunity_id, **kw),
    )
    reg.provide(
        "controltower.dashboard_for_opportunity",
        lambda session, workspace_id, opportunity_id, **kw: factory(
            session
        ).dashboard_for_opportunity(workspace_id, opportunity_id, **kw),
    )
    reg.provide(
        "controltower.portfolio_summary",
        lambda session, workspace_id, **kw: factory(session).portfolio_summary(
            workspace_id, **kw
        ),
    )
    reg.provide(
        "controltower.forecast_for_opportunity",
        lambda session, workspace_id, opportunity_id, **kw: factory(
            session
        ).forecast_for_opportunity(workspace_id, opportunity_id, **kw),
    )
    reg.provide(
        "controltower.response_times_for_opportunity",
        lambda session, workspace_id, opportunity_id: factory(
            session
        ).response_times_for_opportunity(workspace_id, opportunity_id),
    )
    reg.provide(
        "controltower.clause_trends_for_workspace",
        lambda session, workspace_id: factory(
            session
        ).clause_trends_for_workspace(workspace_id),
    )
    reg.provide(
        "controltower.executive_summary_for_opportunity",
        lambda session, workspace_id, opportunity_id, **kw: factory(
            session
        ).executive_summary_for_opportunity(workspace_id, opportunity_id, **kw),
    )
    reg.provide(
        "controltower.payment_schedule_for_opportunity",
        lambda session, workspace_id, opportunity_id: factory(
            session
        ).payment_schedule_for_opportunity(workspace_id, opportunity_id),
    )
    reg.provide(
        "controltower.economics_for_workspace",
        lambda session, workspace_id, **kw: factory(session).economics_for_workspace(
            workspace_id, **kw
        ),
    )
    reg.provide(
        "controltower.customer_outcomes_for_workspace",
        lambda session, workspace_id, **kw: factory(
            session
        ).customer_outcomes_for_workspace(workspace_id, **kw),
    )


module = ModuleSpec(
    name="controltower",
    version="0.2.0",
    router=router,
    soft_deps=(
        "ingestion",
        "claims",
        "change",
        "evidence",
        "findings",
        "outcomes",
        "billing",
    ),
    setup=setup,
)
