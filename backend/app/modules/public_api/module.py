from app.core.module import AppContext, ModuleSpec
from app.modules.public_api.router import router
from app.modules.public_api.service import PublicApiService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry

    def factory(session):
        return PublicApiService(
            session,
            change_factory=reg.get("change.service_factory"),
            publish=ctx.events.publish,
        )

    reg.provide("public_api.service_factory", factory)


module = ModuleSpec(
    name="public_api",
    version="0.1.0",
    router=router,
    soft_deps=("change",),
    setup=setup,
)
