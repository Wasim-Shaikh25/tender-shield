"""fix public_api rls for api key and callback lookups

Revision ID: d56668489ef4
Revises: 2dcc5f291455
Create Date: 2026-08-02 08:09:34.234630
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d56668489ef4"
down_revision: str | Sequence[str] | None = "2dcc5f291455"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _workspace_guc() -> str:
    return "nullif(current_setting('app.workspace_id', true), '')::uuid"


def _drop_policy(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS workspace_isolation ON {table}")


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    workspace_guc = _workspace_guc()

    # public_api_keys: allow lookup by the API key hash during authentication,
    # then enforce workspace isolation for all other operations.
    _drop_policy("public_api_keys")
    op.execute(
        f"""
        CREATE POLICY workspace_isolation ON public_api_keys
        USING (
            workspace_id = {workspace_guc}
            OR key_hash = nullif(current_setting('app.api_key_hash', true), '')
        )
        WITH CHECK (workspace_id = {workspace_guc})
        """
    )

    # public_signature_requests: allow callback reads/writes by the secret
    # external_id after provider-signature verification, otherwise workspace-scoped.
    _drop_policy("public_signature_requests")
    op.execute(
        f"""
        CREATE POLICY workspace_isolation ON public_signature_requests
        USING (
            workspace_id = {workspace_guc}
            OR external_id = nullif(current_setting('app.external_id', true), '')
        )
        WITH CHECK (workspace_id = {workspace_guc})
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    workspace_guc = _workspace_guc()

    _drop_policy("public_api_keys")
    op.execute(
        f"""
        CREATE POLICY workspace_isolation ON public_api_keys
        USING (workspace_id = {workspace_guc})
        WITH CHECK (workspace_id = {workspace_guc})
        """
    )

    _drop_policy("public_signature_requests")
    op.execute(
        f"""
        CREATE POLICY workspace_isolation ON public_signature_requests
        USING (workspace_id = {workspace_guc})
        WITH CHECK (workspace_id = {workspace_guc})
        """
    )
