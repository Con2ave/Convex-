"""add guided session material storage

Revision ID: d8f62c19a4b0
Revises: c4e9a72d1f36
Create Date: 2026-08-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f62c19a4b0'
down_revision: Union[str, Sequence[str], None] = 'c4e9a72d1f36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('session_quizzes', sa.Column('material_storage_key', sa.String(length=255), nullable=True))
    op.add_column('session_quizzes', sa.Column('material_content_type', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('session_quizzes', schema=None) as batch_op:
        batch_op.drop_column('material_content_type')
        batch_op.drop_column('material_storage_key')
