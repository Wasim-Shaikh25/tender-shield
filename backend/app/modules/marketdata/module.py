"""`marketdata` module registration (TS-195, spec §Public interface)."""

from app.core.module import AppContext, ModuleSpec
from app.modules.marketdata.router import router
from app.modules.marketdata.service import MarketDataService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry

    def factory(session):
        return MarketDataService(session)

    reg.provide("marketdata.service_factory", factory)
    reg.provide(
        "marketdata.employer_profile",
        lambda session, family: factory(session).employer_profile(family),
    )
    reg.provide(
        "marketdata.comparable_awards",
        lambda session, opportunity_id, **kwargs: factory(session).comparable_awards(
            opportunity_id, **kwargs
        ),
    )
    reg.provide(
        "marketdata.price_benchmark",
        lambda session, opportunity_id, **kwargs: factory(session).price_benchmark(
            opportunity_id, **kwargs
        ),
    )


module = ModuleSpec(
    name="marketdata",
    version="0.1.0",
    router=router,
    soft_deps=("findings", "rulepacks", "auth"),
    setup=setup,
)
