"""add influence tier fields to user_profiles

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2025-12-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g2b3c4d5e6f7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    # 添加 influence_claimed_season_id 字段
    op.add_column('user_profiles', sa.Column('influence_claimed_season_id', sa.Integer(), nullable=True))
    # 添加 influence_tier_claimed 字段
    op.add_column('user_profiles', sa.Column('influence_tier_claimed', sa.Integer(), nullable=True, server_default='0'))


def downgrade():
    op.drop_column('user_profiles', 'influence_tier_claimed')
    op.drop_column('user_profiles', 'influence_claimed_season_id')
