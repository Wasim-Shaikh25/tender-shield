import logging

from app.core.module import AppContext, ModuleSpec
from app.modules.auth import security as sec
from app.modules.auth.deps import current_principal, require
from app.modules.auth.router import router

logger = logging.getLogger(__name__)


def setup(ctx: AppContext) -> None:
    s = ctx.settings
    if s.jwt_private_key and s.jwt_public_key:
        keys = sec.load_keypair(s.jwt_private_key, s.jwt_public_key)
    else:
        keys = sec.generate_keypair()
        logger.warning(
            "auth: no JWT keys configured — generated an EPHEMERAL keypair "
            "(dev/test only; set TS_JWT_PRIVATE_KEY / TS_JWT_PUBLIC_KEY in prod)"
        )
    ctx.registry.provide("auth.keys", keys)
    # Published for other modules — consumed via the registry, never imported.
    ctx.registry.provide("auth.current_principal", current_principal)
    ctx.registry.provide("auth.require", require)


module = ModuleSpec(
    name="auth",
    version="0.1.0",
    router=router,
    soft_deps=(),
    setup=setup,
)
