"""add arena_card_stats table

Revision ID: 20251219_arena_stats
Revises: 
Create Date: 2025-12-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251219_arena_stats'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'arena_card_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False, comment='卡牌ID，对应cards表的card_id'),
        sa.Column('popularity', sa.Float(), nullable=True, comment='热门度'),
        sa.Column('avg_copies_in_deck', sa.Float(), nullable=True, comment='平均每套牌包含数量'),
        sa.Column('win_rate', sa.Float(), nullable=True, comment='胜率'),
        sa.Column('drawn_win_rate', sa.Float(), nullable=True, comment='抽到时胜率'),
        sa.Column('played_win_rate', sa.Float(), nullable=True, comment='出场胜率'),
        sa.Column('num_games', sa.Integer(), nullable=True, comment='参与对局数'),
        sa.Column('card_class', sa.String(length=20), nullable=False, comment='职业'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
        sa.PrimaryKeyConstraint('id')
    )
    # 创建唯一索引：card_id + card_class
    op.create_index('ix_arena_card_stats_card_class', 'arena_card_stats', ['card_id', 'card_class'], unique=True)


def downgrade():
    op.drop_index('ix_arena_card_stats_card_class', table_name='arena_card_stats')
    op.drop_table('arena_card_stats')
