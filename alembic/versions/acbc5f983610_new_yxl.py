"""new yxl

Revision ID: acbc5f983610
Revises: 06299906280e
Create Date: 2025-12-11 23:33:44.987553

"""

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision = 'acbc5f983610'
down_revision = '06299906280e'



branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("influence", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "user_profiles",
        sa.Column("current_season_rank", sa.Integer(), nullable=True),
    )
    # 去掉 server_default，只保留 Python 层 default=1
    op.alter_column("user_profiles", "influence", server_default=None)


def downgrade() -> None:
    op.drop_column("user_profiles", "current_season_rank")
    op.drop_column("user_profiles", "influence")