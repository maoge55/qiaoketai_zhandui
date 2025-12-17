"""add member_season_ranks table

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2025-12-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'member_season_ranks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('season_id', sa.Integer(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'season_id', name='uq_user_season')
    )
    op.create_index(op.f('ix_member_season_ranks_id'), 'member_season_ranks', ['id'], unique=False)
    op.create_index(op.f('ix_member_season_ranks_season_id'), 'member_season_ranks', ['season_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_member_season_ranks_season_id'), table_name='member_season_ranks')
    op.drop_index(op.f('ix_member_season_ranks_id'), table_name='member_season_ranks')
    op.drop_table('member_season_ranks')
