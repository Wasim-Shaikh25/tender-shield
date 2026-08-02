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
            outcomes_factory=reg.get("outcomes.service_factory"),
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


module = ModuleSpec(
    name="controltower",
    version="0.1.0",
    router=router,
    soft_deps=("ingestion", "claims", "change", "evidence", "outcomes"),
    setup=setup,
)
