import app.modules.analytics.models  # noqa: F401
from app.core.module import AppContext, ModuleSpec
from app.modules.analytics.plan_agent import PlanDashboardAgent
from app.modules.analytics.router import router
from app.modules.analytics.service import AnalyticsService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry

    def _service(session) -> AnalyticsService:
        return AnalyticsService(
            session,
            findings_factory=reg.get("findings.store_factory"),
            ingestion_factory=reg.get("ingestion.service_factory"),
        )

    reg.provide("analytics.service_factory", _service)

    def _plan_dashboard(session, workspace_id, opportunity_id, query, identity=None) -> dict:
        return _service(session).plan_dashboard(
            workspace_id,
            opportunity_id,
            query,
            identity=identity,
            agent=PlanDashboardAgent(),
        )

    reg.provide("analytics.plan_dashboard", _plan_dashboard)


module = ModuleSpec(
    name="analytics",
    version="0.1.0",
    router=router,
    soft_deps=("findings", "ingestion"),
    setup=setup,
)
