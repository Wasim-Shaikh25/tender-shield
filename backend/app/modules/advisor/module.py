from app.core.module import AppContext, ModuleSpec
from app.modules.advisor.router import router
from app.modules.advisor.service import AdvisorService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry

    def factory(session):
        return AdvisorService(
            session,
            billing_factory=reg.get("billing.service_factory"),
            publish=ctx.events.publish,
        )

    reg.provide("advisor.service_factory", factory)


module = ModuleSpec(
    name="advisor",
    version="0.1.0",
    router=router,
    soft_deps=("billing", "export"),
    setup=setup,
)
