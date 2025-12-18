"""add article pinned_at

Revision ID: a1b2c3d4e5f6
Revises: h3b4c5d6e7f8
Create Date: 2025-12-18

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'h3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('articles', sa.Column('pinned_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('articles', 'pinned_at')
