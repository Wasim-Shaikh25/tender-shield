from app.core.module import AppContext, ModuleSpec
from app.modules.review.router import router
from app.modules.review.service import ReviewService


def setup(ctx: AppContext) -> None:
    reg = ctx.registry
    # Published so drafting/export can check the review gate before producing
    # or exporting artifacts (Doc §11.4) — consumed via the registry.
    reg.provide(
        "review.service_factory",
        lambda session: ReviewService(session, store_factory=reg.get("findings.store_factory")),
    )


module = ModuleSpec(
    name="review",
    version="0.1.0",
    router=router,
    soft_deps=("findings", "auth"),
    setup=setup,
)
