"""add best_season_score to user_profiles

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2025-12-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user_profiles', sa.Column('best_season_score', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('user_profiles', 'best_season_score')
