"""add current_season_score to user_profiles

Revision ID: d4e5f6a7b8c9
Revises: c1a2b3c4d5e6
Create Date: 2025-12-15

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    # 添加当前赛季分数字段
    op.add_column(
        'user_profiles',
        sa.Column('current_season_score', sa.Integer(), nullable=True)
    )


def downgrade():
    op.drop_column('user_profiles', 'current_season_score')
