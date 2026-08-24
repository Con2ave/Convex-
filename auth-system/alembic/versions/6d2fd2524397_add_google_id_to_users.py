"""add google_id to users for Google sign-in account linking

Revision ID: 6d2fd2524397
Revises: c4e9a72d1f36
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d2fd2524397'
down_revision: Union[str, Sequence[str], None] = 'c4e9a72d1f36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('google_id', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_users_google_id'), 'users', ['google_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_users_google_id'), table_name='users')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('google_id')
