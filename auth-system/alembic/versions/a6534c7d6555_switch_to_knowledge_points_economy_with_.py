"""switch to Knowledge Points economy with tiered redemption

Revision ID: a6534c7d6555
Revises: b67442655796
Create Date: 2026-07-08 21:50:05.822730

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6534c7d6555'
down_revision: Union[str, Sequence[str], None] = 'b67442655796'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite can't ALTER COLUMN in place - batch mode recreates the table under the hood.
    # ghs_amount is added with a transient server_default so it satisfies NOT NULL on any
    # pre-existing rows (dev/test data only - this app predates any real redemption history),
    # then the default is dropped so future inserts must supply it explicitly, matching the model.
    with op.batch_alter_table('redemptions') as batch_op:
        batch_op.add_column(sa.Column('ghs_amount', sa.Integer(), nullable=False, server_default='0'))
        batch_op.alter_column('points_spent',
                   existing_type=sa.NUMERIC(precision=10, scale=2),
                   type_=sa.Integer(),
                   existing_nullable=False)
    with op.batch_alter_table('redemptions') as batch_op:
        batch_op.alter_column('ghs_amount', server_default=None)

    with op.batch_alter_table('reward_ledger') as batch_op:
        batch_op.alter_column('points',
                   existing_type=sa.NUMERIC(precision=10, scale=2),
                   type_=sa.Integer(),
                   existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('reward_ledger') as batch_op:
        batch_op.alter_column('points',
                   existing_type=sa.Integer(),
                   type_=sa.NUMERIC(precision=10, scale=2),
                   existing_nullable=False)
    with op.batch_alter_table('redemptions') as batch_op:
        batch_op.alter_column('points_spent',
                   existing_type=sa.Integer(),
                   type_=sa.NUMERIC(precision=10, scale=2),
                   existing_nullable=False)
        batch_op.drop_column('ghs_amount')
