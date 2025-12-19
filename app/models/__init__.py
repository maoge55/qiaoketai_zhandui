from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    UnicodeText,
    ForeignKey,
    Enum as SAEnum,
    Float,
    Boolean,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class UserRole(str, Enum):
    VISITOR = "visitor"
    USER = "user"
    MEMBER = "member"
    ELITE_MEMBER = "elite_member"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(50), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    role = Column(
        SAEnum(UserRole, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.USER,
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    profile = relationship(
        "UserProfile", back_populates="user", uselist=False
    )
    articles = relationship("Article", back_populates="author")
    comments = relationship("Comment", back_populates="user")
    achievements = relationship("Achievement", back_populates="member")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    avatar_url = Column(String(255), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)
    strength_score = Column(String(20), nullable=True)
    bio = Column(Text, nullable=True)
    avg_arena_wins = Column(Float, nullable=True)
    arena_best_rank = Column(String(255), nullable=True)
    other_tags = Column(String(255), nullable=True)
    # ✅ 新增：影响力（默认 1），数值越大影响力越高
    influence = Column(Integer, nullable=False, default=1)
    # ✅ 新增：当前赛季排名（1 表示第一名，数字越小越靠前）
    current_season_rank = Column(Integer, nullable=True)
    # ✅ 新增：当前赛季分数（分数越高越厉害）
    current_season_score = Column(Integer, nullable=True)
    # ✅ 新增：历史最高分数
    best_season_score = Column(Integer, nullable=True)
    # ✅ 新增：已获得影响力奖励的赛季ID（用于判断是否新赛季重置）
    influence_claimed_season_id = Column(Integer, nullable=True)
    # ✅ 新增：当前赛季已获得的最高影响力档位 (0=无, 1=前500, 2=前200, 3=前50, 4=前10, 5=前3, 6=第1)
    influence_tier_claimed = Column(Integer, nullable=True, default=0)
    user = relationship("User", back_populates="profile")


class ArticleStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DELETED = "deleted"


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    status = Column(SAEnum(ArticleStatus), default=ArticleStatus.DRAFT)
    category = Column(String(50), nullable=True)
    is_featured = Column(Boolean, default=False)

    # ✅ 攻略投票计数
    upvote_count = Column(Integer, nullable=False, default=0)
    downvote_count = Column(Integer, nullable=False, default=0)

    # ✅ 置顶时间（非空则置顶，按时间倒序排，后置顶的在前面）
    pinned_at = Column(DateTime, nullable=True, default=None)

    author = relationship("User", back_populates="articles")
    tags = relationship("ArticleTag", back_populates="article")
    comments = relationship("Comment", back_populates="article")


class ArticleTag(Base):
    __tablename__ = "article_tags"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(
        Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    tag_name = Column(String(50), nullable=False)

    article = relationship("Article", back_populates="tags")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(
        Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    # SQL Server 下使用 NVARCHAR(MAX) 以支持 Emoji/Unicode
    content = Column(UnicodeText, nullable=False)
    # ✅ 新增：置顶
    is_pinned = Column(Boolean, nullable=False, default=False)
    pinned_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    article = relationship("Article", back_populates="comments")
    user = relationship("User", back_populates="comments")
    parent = relationship("Comment", remote_side=[id], backref="replies")

class CardReview(Base):
    __tablename__ = "card_reviews"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("cards.id", ondelete="CASCADE"), index=True, nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    score = Column(Float, nullable=False)           # 1-10 或 0-100 都可以
    content = Column(Text, nullable=False)
    game_version = Column(String(32), nullable=True)  # 例如 "29.2"
    created_at = Column(DateTime, default=datetime.utcnow)

    # ✅ 点评投票计数
    upvote_count = Column(Integer, nullable=False, default=0)
    downvote_count = Column(Integer, nullable=False, default=0)

    card = relationship("Card", back_populates="reviews")
    reviewer = relationship("User")


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, nullable=True, unique=True, index=True)
    name = Column(String(255), nullable=False)
    expansion = Column(String(100), nullable=False, index=True)
    mana_cost = Column(Integer, nullable=False)
    card_class = Column(String(50), nullable=False)
    rarity = Column(String(50), nullable=False)
    version = Column(String(50), nullable=True)
    pic = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    arena_score = Column(Integer, nullable=True)
    arena_win_rates = Column(JSON, default=list)
    short_review = Column(String(255), nullable=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewer = relationship("User")  # 如果你已经有就不要重复写
    reviews = relationship(
        "CardReview",
        back_populates="card",
        cascade="all, delete-orphan",
    )

    @property
    def reviewer_nickname(self):
        return self.reviewer.nickname if self.reviewer else None



class AchievementStatus(str, Enum):
    ACTIVE = "active"          # 展示在前台
    ARCHIVED = "archived"      # 下架但保留数据
    DELETED = "deleted"        # 逻辑删除


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    season_or_version = Column(String(100), nullable=True)
    rank_or_result = Column(String(100), nullable=True)
    achieved_at = Column(DateTime, nullable=True)
    status = Column(
        SAEnum(AchievementStatus),
        nullable=False,
        default=AchievementStatus.ACTIVE,
    )
    is_pinned = Column(Boolean, nullable=False, default=False)

    member = relationship("User", back_populates="achievements")


class HomepageConfig(Base):
    __tablename__ = "homepage_config"

    id = Column(Integer, primary_key=True, index=True)
    team_logo_url = Column(String(255), nullable=True)
    banner_images = Column(JSON, nullable=True)
    featured_achievements = Column(JSON, nullable=True)
    featured_members = Column(JSON, nullable=True)
    # ✅ 竞技场卡池版本列表（JSON 数组）
    arena_pool_versions = Column(JSON, nullable=True)


class EmailVerificationCode(Base):
    __tablename__ = "email_verification_codes"
    __table_args__ = (
        UniqueConstraint("email", "code", name="uq_email_code"),
    )

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False)
    code = Column(String(10), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)


class MemberSeasonRank(Base):
    """战队成员历史榜单统计表"""
    __tablename__ = "member_season_ranks"
    __table_args__ = (
        UniqueConstraint("user_id", "season_id", name="uq_user_season"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    season_id = Column(Integer, nullable=False, index=True)
    rank = Column(Integer, nullable=True)  # 最终排名
    score = Column(Integer, nullable=True)  # 最终分数
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


class CardReviewVote(Base):
    """用户对卡牌点评的点赞/拉踩状态（互斥）。"""

    __tablename__ = "card_review_votes"
    __table_args__ = (
        UniqueConstraint("review_id", "user_id", name="uq_review_user_vote"),
    )

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(
        Integer,
        ForeignKey("card_reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    # 1=up, -1=down
    action_type = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class GuideVote(Base):
    """用户对攻略文章的点赞/拉踩状态（互斥）。"""

    __tablename__ = "guide_votes"
    __table_args__ = (
        UniqueConstraint("article_id", "user_id", name="uq_guide_user_vote"),
    )

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(
        Integer,
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    # 1=up, -1=down
    action_type = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Notification(Base):
    """全局通知：评论触发，发送给文章作者。"""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=False, index=True)
    is_read = Column(Boolean, nullable=False, default=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ArenaCardStats(Base):
    """竞技场卡牌统计数据（来自 HSReplay）"""

    __tablename__ = "arena_card_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    card_id = Column(Integer, nullable=False, index=True, comment="卡牌ID，对应cards表的card_id")
    popularity = Column(Float, nullable=True, comment="热门度")
    avg_copies_in_deck = Column(Float, nullable=True, comment="平均每套牌包含数量")
    win_rate = Column(Float, nullable=True, comment="胜率")
    drawn_win_rate = Column(Float, nullable=True, comment="抽到时胜率")
    played_win_rate = Column(Float, nullable=True, comment="出场胜率")
    num_games = Column(Integer, nullable=True, comment="参与对局数")
    card_class = Column(String(20), nullable=False, comment="职业")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('card_id', 'card_class', name='uix_arena_card_stats_card_class'),
    )
