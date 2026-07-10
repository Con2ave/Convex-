"""add guided session target fields and session quizzes table

Revision ID: c4e9a72d1f36
Revises: 0bd8614b5afe
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e9a72d1f36'
down_revision: Union[str, Sequence[str], None] = '0bd8614b5afe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('study_sessions', sa.Column('target_minutes', sa.Integer(), nullable=True))
    op.add_column('study_sessions', sa.Column('target_time_met', sa.Boolean(), nullable=True))

    op.create_table('session_quizzes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('questions', sa.JSON(), nullable=True),
    sa.Column('answers', sa.JSON(), nullable=True),
    sa.Column('score', sa.Integer(), nullable=True),
    sa.Column('passed', sa.Boolean(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('source_filename', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['study_sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('session_id')
    )
    op.create_index(op.f('ix_session_quizzes_id'), 'session_quizzes', ['id'], unique=False)
    op.create_index(op.f('ix_session_quizzes_session_id'), 'session_quizzes', ['session_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_session_quizzes_session_id'), table_name='session_quizzes')
    op.drop_index(op.f('ix_session_quizzes_id'), table_name='session_quizzes')
    op.drop_table('session_quizzes')

    with op.batch_alter_table('study_sessions', schema=None) as batch_op:
        batch_op.drop_column('target_time_met')
        batch_op.drop_column('target_minutes')
