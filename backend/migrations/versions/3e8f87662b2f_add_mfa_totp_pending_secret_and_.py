"""Add mfa_totp_pending_secret and invitation token_hash

Revision ID: 3e8f87662b2f
Revises: df4721874c4d
Create Date: 2026-07-30 05:12:19.501177
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = '3e8f87662b2f'
down_revision: str | None = 'df4721874c4d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _backfill_token_hash(conn) -> None:
    rows = conn.execute(text("SELECT id, token FROM invitations WHERE token_hash IS NULL")).all()
    for row in rows:
        token_hash = hashlib.sha256(str(row.token).encode()).hexdigest()
        conn.execute(
            text("UPDATE invitations SET token_hash = :h WHERE id = :id"),
            {"h": token_hash, "id": str(row.id)},
        )


def upgrade() -> None:
    # Add TOTP pending-secret column used during MFA enrollment (TS-127).
    op.add_column('users', sa.Column('mfa_totp_pending_secret', sa.String(), nullable=True))

    # Replace plaintext Invitation.token with token_hash (TS-126).
    # Add nullable first so existing rows can be back-filled before enforcing NOT NULL.
    op.add_column('invitations', sa.Column('token_hash', sa.String(), nullable=True))
    _backfill_token_hash(op.get_bind())

    # SQLite cannot ALTER constraints, so use batch mode there.
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table('invitations') as batch_op:
            batch_op.create_unique_constraint('uq_invitations_token_hash', ['token_hash'])
            batch_op.alter_column('token_hash', nullable=False)
            batch_op.drop_column('token')
    else:
        op.create_unique_constraint('uq_invitations_token_hash', 'invitations', ['token_hash'])
        op.alter_column('invitations', 'token_hash', nullable=False)
        op.drop_column('invitations', 'token')


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table('invitations') as batch_op:
            batch_op.add_column(sa.Column('token', sa.String(), nullable=False))
            batch_op.drop_constraint('uq_invitations_token_hash', type_='unique')
            batch_op.drop_column('token_hash')
    else:
        op.add_column('invitations', sa.Column('token', sa.String(), nullable=False))
        op.drop_constraint('uq_invitations_token_hash', 'invitations', type_='unique')
        op.drop_column('invitations', 'token_hash')
    op.drop_column('users', 'mfa_totp_pending_secret')
