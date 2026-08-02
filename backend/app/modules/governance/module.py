"""Governance module (TS-332, TS-340)."""

from app.core.module import AppContext, ModuleSpec
from app.core.storage import get_storage
from app.modules.governance.router import router
from app.modules.governance.service import GovernanceService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    storage = get_storage(ctx.settings)

    reg.provide(
        "governance.settings_for_workspace",
        lambda session, workspace_id: GovernanceService(
            session, publish=ctx.events.publish
        ).get_settings(workspace_id),
    )
    reg.provide(
        "governance.service_factory",
        lambda session: GovernanceService(
            session,
            ingestion_retention=reg.get("ingestion.documents_for_retention"),
            ingestion_apply=reg.get("ingestion.retention_apply"),
            review_factory=reg.get("review.service_factory"),
            storage=storage,
            settings=ctx.settings,
            publish=ctx.events.publish,
        ),
    )
    reg.provide(
        "governance.retention_job",
        lambda: _run_retention_job(ctx),
    )

    scheduler = reg.get("core.scheduler")
    if scheduler is not None and ctx.settings.retention_job_enabled:
        scheduler.add_job(
            reg.get("governance.retention_job"),
            "interval",
            hours=ctx.settings.retention_job_interval_hours,
        )


async def _run_retention_job(ctx: AppContext) -> None:
    """Open a short-lived DB session and run the retention job."""
    engine = ctx.registry.get("db.engine")
    if engine is None:
        return
    storage = get_storage(ctx.settings)
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        svc = GovernanceService(
            session,
            ingestion_retention=ctx.registry.get("ingestion.documents_for_retention"),
            ingestion_apply=ctx.registry.get("ingestion.retention_apply"),
            review_factory=ctx.registry.get("review.service_factory"),
            storage=storage,
            settings=ctx.settings,
            publish=ctx.events.publish,
        )
        await svc.run_retention_job()
        session.commit()


module = ModuleSpec(
    name="governance",
    version="0.1.0",
    router=router,
    soft_deps=("ingestion", "review"),
    setup=setup,
)
