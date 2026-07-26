import logging

from app.core.module import AppContext, ModuleSpec
from app.modules.auth import security as sec
from app.modules.auth.deps import authenticate, check_role
from app.modules.auth.router import router
from app.modules.auth.workspaces import WorkspaceAdmin

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
    # Cross-module API — consumed via app.core.deps by capability name, never imported.
    ctx.registry.provide("auth.authenticate", authenticate)
    ctx.registry.provide("auth.check_role", check_role)
    ctx.registry.provide("auth.workspace_factory", lambda session: WorkspaceAdmin(session))


module = ModuleSpec(
    name="auth",
    version="0.1.0",
    router=router,
    soft_deps=(),
    setup=setup,
)
