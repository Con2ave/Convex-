"""add network field to redemptions for paystack

Revision ID: 3003e874ef3d
Revises: a6534c7d6555
Create Date: 2026-07-08 23:28:23.067676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3003e874ef3d'
down_revision: Union[str, Sequence[str], None] = 'a6534c7d6555'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite needs batch mode to add a NOT NULL column to a table that may already have rows.
    # 'mtn' is a reasonable backfill default (dev/test data only - no real redemptions have
    # been sent through this app yet); the default is dropped after so future inserts must
    # supply it explicitly, matching the model.
    with op.batch_alter_table('redemptions') as batch_op:
        batch_op.add_column(sa.Column('network', sa.String(length=20), nullable=False, server_default='mtn'))
    with op.batch_alter_table('redemptions') as batch_op:
        batch_op.alter_column('network', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('redemptions') as batch_op:
        batch_op.drop_column('network')
