"""add comment pinning

Revision ID: bf3c2d9a7c10
Revises: acbc5f983610
Create Date: 2025-12-12

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bf3c2d9a7c10"
down_revision = "acbc5f983610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQL Server 下 Boolean 映射为 BIT，默认值用 0/1
    op.add_column(
        "comments",
        sa.Column(
            "is_pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "comments",
        sa.Column("pinned_at", sa.DateTime(), nullable=True),
    )

    # 去掉 server_default，避免未来修改时产生意外
    op.alter_column("comments", "is_pinned", server_default=None)


def downgrade() -> None:
    op.drop_column("comments", "pinned_at")
    op.drop_column("comments", "is_pinned")
