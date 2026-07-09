"""change reward points to decimal for GHS precision

Revision ID: b67442655796
Revises: 07e54df91c64
Create Date: 2026-07-08 21:38:57.415084

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b67442655796'
down_revision: Union[str, Sequence[str], None] = '07e54df91c64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite can't ALTER COLUMN a type in place - batch mode recreates the table under the hood.
    with op.batch_alter_table('redemptions') as batch_op:
        batch_op.alter_column('points_spent',
                   existing_type=sa.INTEGER(),
                   type_=sa.Numeric(precision=10, scale=2),
                   existing_nullable=False)
    with op.batch_alter_table('reward_ledger') as batch_op:
        batch_op.alter_column('points',
                   existing_type=sa.INTEGER(),
                   type_=sa.Numeric(precision=10, scale=2),
                   existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('reward_ledger') as batch_op:
        batch_op.alter_column('points',
                   existing_type=sa.Numeric(precision=10, scale=2),
                   type_=sa.INTEGER(),
                   existing_nullable=False)
    with op.batch_alter_table('redemptions') as batch_op:
        batch_op.alter_column('points_spent',
                   existing_type=sa.Numeric(precision=10, scale=2),
                   type_=sa.INTEGER(),
                   existing_nullable=False)
