from app.core.module import AppContext, ModuleSpec
from app.modules.notifications.adapters import build_sender
from app.modules.notifications.sender import Message


def setup(ctx: AppContext) -> None:
    # ConsoleSender in dev/test; SES/MSG91 adapters register when credentials are set.
    sender = build_sender(ctx.settings)
    ctx.registry.provide("notifications.sender", sender)

    scheduler = ctx.registry.get("core.scheduler")
    if scheduler is not None:

        def _stub_digest_tick() -> None:
            # TS-091: stub daily deadline digest; replace with real cross-workspace
            # deadline query + per-user delivery once background jobs are needed.
            sender.send(
                Message(
                    channel="email",
                    to="scheduler-stub@example.com",
                    subject="TenderShield deadline digest",
                    body="scheduler tick placeholder",
                )
            )

        scheduler.add_job(_stub_digest_tick, "interval", hours=24)


module = ModuleSpec(
    name="notifications",
    version="0.1.0",
    router=None,
    soft_deps=("ingestion",),
    setup=setup,
)
