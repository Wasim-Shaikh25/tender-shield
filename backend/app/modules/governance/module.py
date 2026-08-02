"""Governance module (TS-332)."""

from app.core.module import AppContext, ModuleSpec
from app.modules.governance.router import router
from app.modules.governance.service import GovernanceService


def setup(ctx: AppContext) -> None:
    ctx.registry.provide(
        "governance.settings_for_workspace",
        lambda session, workspace_id: GovernanceService(
            session, publish=ctx.events.publish
        ).get_settings(workspace_id),
    )
    ctx.registry.provide(
        "governance.service_factory",
        lambda session: GovernanceService(
            session,
            ingestion_retention=ctx.registry.get("ingestion.documents_for_retention"),
            publish=ctx.events.publish,
        ),
    )


module = ModuleSpec(
    name="governance",
    version="0.1.0",
    router=router,
    soft_deps=("ingestion",),
    setup=setup,
)
