"""Alembic environment.

Model discovery is pluggable: every enabled module may expose a `models`
submodule; importing it registers that module's tables on Base.metadata. This
file is infrastructure, not a feature module, so it is permitted to import
across modules (the architecture test only constrains app/modules/**).
"""

from __future__ import annotations

import importlib
import logging

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import Settings
from app.core.db import Base
from app.core.loader import discover_module_names

logger = logging.getLogger("alembic.env")

config = context.config
settings = Settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def _import_module_models() -> None:
    for name in discover_module_names():
        try:
            importlib.import_module(f"app.modules.{name}.models")
        except ModuleNotFoundError:
            continue  # module owns no tables (yet)
        except Exception:
            logger.exception("failed importing models for module %r", name)


_import_module_models()
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
