from app.core.module import AppContext, ModuleSpec
from app.modules.standards.router import router
from app.modules.standards.service import OrgCommercialStandardsService, OrgStandardsService


def setup(ctx: AppContext) -> None:
    # Published so the baseline module can merge the org's custom notice
    # standard onto universal+regional without importing this module.
    ctx.registry.provide(
        "standards.org_notice_provider",
        lambda session: OrgStandardsService(session),
    )
    ctx.registry.provide(
        "standards.commercial_service_factory",
        lambda session: OrgCommercialStandardsService(session),
    )


module = ModuleSpec(
    name="standards",
    version="0.1.0",
    router=router,
    soft_deps=("auth", "findings"),
    setup=setup,
)
