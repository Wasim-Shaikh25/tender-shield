from app.core.module import AppContext, ModuleSpec
from app.modules.integrations.router import router
from app.modules.integrations.service import IntegrationsService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry

    def factory(session):
        return IntegrationsService(
            session,
            ingestion_factory=reg.get("ingestion.service_factory"),
            change_factory=reg.get("change.service_factory"),
            publish=ctx.events.publish,
        )

    reg.provide("integrations.service_factory", factory)
    reg.provide(
        "integrations.adapters_for_workspace",
        lambda session, workspace_id: factory(session).list_sources(workspace_id),
    )
    reg.provide(
        "integrations.import_from_source",
        lambda session, workspace_id, source_id, user_id, payload: factory(
            session
        ).import_from_source(workspace_id, source_id, user_id, payload),
    )
    reg.provide(
        "integrations.schedule_activities_for_opportunity",
        lambda session, workspace_id, opportunity_id: factory(
            session
        ).list_schedule_activities(workspace_id, opportunity_id),
    )


module = ModuleSpec(
    name="integrations",
    version="0.1.0",
    router=router,
    soft_deps=("ingestion", "change"),
    setup=setup,
)
