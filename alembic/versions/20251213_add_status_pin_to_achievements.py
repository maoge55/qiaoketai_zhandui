"""add status and pin to achievements

Revision ID: 20251213_add_status_pin
Revises: bf3c2d9a7c10
Create Date: 2025-12-13
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251213_add_status_pin'
down_revision = 'bf3c2d9a7c10'
branch_labels = None
depends_on = None


achievement_status_enum = sa.Enum(
    'active',
    'archived',
    'deleted',
    name='achievementstatus',
)


def upgrade() -> None:
    op.add_column(
        'achievements',
        sa.Column(
            'status',
            achievement_status_enum,
            nullable=False,
            server_default='active',
        ),
    )
    op.add_column(
        'achievements',
        sa.Column(
            'is_pinned',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column('achievements', 'status', server_default=None)
    op.alter_column('achievements', 'is_pinned', server_default=None)


def downgrade() -> None:
    op.drop_column('achievements', 'is_pinned')
    op.drop_column('achievements', 'status')
    try:
        achievement_status_enum.drop(op.get_bind(), checkfirst=True)
    except Exception:
        # Enum cleanup best-effort; ignore if backend does not support drop
        pass
