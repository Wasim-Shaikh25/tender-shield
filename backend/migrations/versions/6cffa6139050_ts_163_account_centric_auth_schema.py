"""TS-163 account-centric auth schema

Revision ID: 6cffa6139050
Revises: 3e8f87662b2f
Create Date: 2026-07-30 05:29:16.266352
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '6cffa6139050'
down_revision: str | None = '3e8f87662b2f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create the mobile verification table.
    op.create_table(
        'mobile_verifications',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_mobile_verifications_user_id'), 'mobile_verifications', ['user_id'], unique=False)

    # Add the new account-centric columns and remove OIDC columns.
    # SQLite cannot alter column constraints directly, so use batch_alter_table there.
    # PostgreSQL can add/alter/drop individual columns without recreating the table,
    # which avoids dropping the users primary key while foreign keys reference it.
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table('users', recreate='always') as batch_op:
            batch_op.add_column(sa.Column('org_name', sa.String(), nullable=True))
            batch_op.add_column(sa.Column('dob', sa.Date(), nullable=True))
            batch_op.add_column(sa.Column('city', sa.String(), nullable=True))
            batch_op.add_column(sa.Column('mobile_verified', sa.Boolean(), nullable=True))

        op.execute(
            "UPDATE users SET org_name = '', city = '', mobile_verified = 0, "
            "phone = COALESCE(phone, ''), password_hash = COALESCE(password_hash, '')"
        )

        with op.batch_alter_table('users', recreate='always') as batch_op:
            batch_op.alter_column('org_name', existing_type=sa.String(), nullable=False)
            batch_op.alter_column('city', existing_type=sa.String(), nullable=False)
            batch_op.alter_column('mobile_verified', existing_type=sa.Boolean(), nullable=False)
            batch_op.alter_column('phone', existing_type=sa.VARCHAR(), nullable=False)
            batch_op.alter_column('password_hash', existing_type=sa.VARCHAR(), nullable=False)
            batch_op.drop_column('apple_id')
            batch_op.drop_column('google_sub')
    else:
        op.add_column('users', sa.Column('org_name', sa.String(), nullable=True))
        op.add_column('users', sa.Column('dob', sa.Date(), nullable=True))
        op.add_column('users', sa.Column('city', sa.String(), nullable=True))
        op.add_column('users', sa.Column('mobile_verified', sa.Boolean(), nullable=True))

        op.execute(
            "UPDATE users SET org_name = '', city = '', mobile_verified = false, "
            "phone = COALESCE(phone, ''), password_hash = COALESCE(password_hash, '')"
        )

        op.alter_column('users', 'org_name', existing_type=sa.String(), nullable=False)
        op.alter_column('users', 'city', existing_type=sa.String(), nullable=False)
        op.alter_column('users', 'mobile_verified', existing_type=sa.Boolean(), nullable=False)
        op.alter_column('users', 'phone', existing_type=sa.VARCHAR(), nullable=False)
        op.alter_column('users', 'password_hash', existing_type=sa.VARCHAR(), nullable=False)
        op.drop_column('users', 'apple_id')
        op.drop_column('users', 'google_sub')


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table('users', recreate='always') as batch_op:
            batch_op.add_column(sa.Column('google_sub', sa.VARCHAR(), nullable=True))
            batch_op.add_column(sa.Column('apple_id', sa.VARCHAR(), nullable=True))
            batch_op.alter_column('password_hash', existing_type=sa.VARCHAR(), nullable=True)
            batch_op.alter_column('phone', existing_type=sa.VARCHAR(), nullable=True)
            batch_op.drop_column('mobile_verified')
            batch_op.drop_column('city')
            batch_op.drop_column('dob')
            batch_op.drop_column('org_name')
    else:
        op.add_column('users', sa.Column('google_sub', sa.VARCHAR(), nullable=True))
        op.add_column('users', sa.Column('apple_id', sa.VARCHAR(), nullable=True))
        op.alter_column('users', 'password_hash', existing_type=sa.VARCHAR(), nullable=True)
        op.alter_column('users', 'phone', existing_type=sa.VARCHAR(), nullable=True)
        op.drop_column('users', 'mobile_verified')
        op.drop_column('users', 'city')
        op.drop_column('users', 'dob')
        op.drop_column('users', 'org_name')

    op.drop_index(op.f('ix_mobile_verifications_user_id'), table_name='mobile_verifications')
    op.drop_table('mobile_verifications')
