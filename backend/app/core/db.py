"""Database foundation: declarative base, engine/session factory, RLS helpers.

Table ownership lives with the modules (specs/data-model.md); this file owns the
shared machinery only. Org-scoped tables mix in OrgScopedMixin so the RLS
migration can enumerate them, and every request binds its org via
bind_org_context (Doc §3.2, §5 — the RLS binding is non-negotiable).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Uuid, create_engine, func, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    declared_attr,
    mapped_column,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from app.core.config import Settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# Tables that must carry an org-isolation RLS policy (Doc §3.2 — non-negotiable).
# Populated as OrgScopedMixin subclasses are defined by their owning modules.
ORG_SCOPED_TABLES: set[str] = set()


class OrgScopedMixin:
    """Adds org_id and registers the table for RLS policy generation."""

    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805 - SQLAlchemy convention
        name = getattr(cls, "_tablename_", None) or cls.__name__.lower()
        ORG_SCOPED_TABLES.add(name)
        return name


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def rls_statements(table: str) -> list[str]:
    """RLS enable + org-isolation policy for one table (PostgreSQL only)."""
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        (
            f"CREATE POLICY org_isolation ON {table} "
            "USING (org_id = current_setting('app.org_id')::uuid)"
        ),
    ]


def bind_org_context(session: Session, org_id: uuid.UUID | str) -> None:
    """SET LOCAL app.org_id for the current transaction — the RLS binding every
    request must perform before touching org data (Doc §5, §3.2).

    A no-op on SQLite (tests): SQLite has no RLS, so cross-org isolation is
    exercised by dedicated integration tests against PostgreSQL.
    """
    if session.get_bind().dialect.name != "postgresql":
        logger.debug("bind_org_context is a no-op on non-PostgreSQL dialects")
        return
    session.execute(text("SET LOCAL app.org_id = :org_id"), {"org_id": str(org_id)})


def make_engine(settings: Settings) -> Engine:
    url = settings.database_url
    if url.startswith("sqlite"):
        # In-memory / single-file SQLite for tests: share one connection so the
        # schema created in a fixture is visible to the app under test.
        return create_engine(
            url,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool if ":memory:" in url else None,
        )
    return create_engine(url, future=True, pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
