"""add arena_pool_versions to homepage_config

Revision ID: c1a2b3c4d5e6
Revises: bf3c2d9a7c10
Create Date: 2025-01-23

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c1a2b3c4d5e6'
down_revision = '20251213_add_status_pin'
branch_labels = None
depends_on = None


def upgrade():
    # 添加竞技场卡池版本字段
    op.add_column(
        'homepage_config',
        sa.Column('arena_pool_versions', sa.JSON(), nullable=True)
    )


def downgrade():
    op.drop_column('homepage_config', 'arena_pool_versions')
