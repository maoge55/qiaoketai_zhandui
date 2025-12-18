"""add votes and notifications

Revision ID: h3b4c5d6e7f8
Revises: g2b3c4d5e6f7
Create Date: 2025-12-18

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "h3b4c5d6e7f8"
down_revision = "g2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- card_reviews vote counts ----
    op.add_column(
        "card_reviews",
        sa.Column("upvote_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "card_reviews",
        sa.Column("downvote_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    # ---- articles vote counts ----
    op.add_column(
        "articles",
        sa.Column("upvote_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "articles",
        sa.Column("downvote_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    # ---- comments content unicode ----
    op.alter_column(
        "comments",
        "content",
        existing_type=sa.Text(),
        type_=sa.UnicodeText(),
        existing_nullable=False,
    )

    # ---- votes tables ----
    op.create_table(
        "card_review_votes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["review_id"], ["card_reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_id", "user_id", name="uq_review_user_vote"),
    )
    op.create_index(op.f("ix_card_review_votes_id"), "card_review_votes", ["id"], unique=False)
    op.create_index(op.f("ix_card_review_votes_review_id"), "card_review_votes", ["review_id"], unique=False)
    op.create_index(op.f("ix_card_review_votes_user_id"), "card_review_votes", ["user_id"], unique=False)

    op.create_table(
        "guide_votes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", "user_id", name="uq_guide_user_vote"),
    )
    op.create_index(op.f("ix_guide_votes_id"), "guide_votes", ["id"], unique=False)
    op.create_index(op.f("ix_guide_votes_article_id"), "guide_votes", ["article_id"], unique=False)
    op.create_index(op.f("ix_guide_votes_user_id"), "guide_votes", ["user_id"], unique=False)

    # ---- notifications ----
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("receiver_id", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("comment_id", sa.Integer(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["receiver_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)
    op.create_index(op.f("ix_notifications_sender_id"), "notifications", ["sender_id"], unique=False)
    op.create_index(op.f("ix_notifications_receiver_id"), "notifications", ["receiver_id"], unique=False)
    op.create_index(op.f("ix_notifications_article_id"), "notifications", ["article_id"], unique=False)
    op.create_index(op.f("ix_notifications_comment_id"), "notifications", ["comment_id"], unique=False)

    # 清理 server_default
    op.alter_column("card_reviews", "upvote_count", server_default=None)
    op.alter_column("card_reviews", "downvote_count", server_default=None)
    op.alter_column("articles", "upvote_count", server_default=None)
    op.alter_column("articles", "downvote_count", server_default=None)
    op.alter_column("notifications", "is_read", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_comment_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_article_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_receiver_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_sender_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
    op.drop_table("notifications")

    op.drop_index(op.f("ix_guide_votes_user_id"), table_name="guide_votes")
    op.drop_index(op.f("ix_guide_votes_article_id"), table_name="guide_votes")
    op.drop_index(op.f("ix_guide_votes_id"), table_name="guide_votes")
    op.drop_table("guide_votes")

    op.drop_index(op.f("ix_card_review_votes_user_id"), table_name="card_review_votes")
    op.drop_index(op.f("ix_card_review_votes_review_id"), table_name="card_review_votes")
    op.drop_index(op.f("ix_card_review_votes_id"), table_name="card_review_votes")
    op.drop_table("card_review_votes")

    op.alter_column(
        "comments",
        "content",
        existing_type=sa.UnicodeText(),
        type_=sa.Text(),
        existing_nullable=False,
    )

    op.drop_column("articles", "downvote_count")
    op.drop_column("articles", "upvote_count")
    op.drop_column("card_reviews", "downvote_count")
    op.drop_column("card_reviews", "upvote_count")
