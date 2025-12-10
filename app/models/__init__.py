from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
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


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(50), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    role = Column(SAEnum(UserRole), default=UserRole.USER, nullable=False)
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
    content = Column(Text, nullable=False)
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



class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    season_or_version = Column(String(100), nullable=True)
    rank_or_result = Column(String(100), nullable=True)
    achieved_at = Column(DateTime, nullable=True)

    member = relationship("User", back_populates="achievements")


class HomepageConfig(Base):
    __tablename__ = "homepage_config"

    id = Column(Integer, primary_key=True, index=True)
    team_logo_url = Column(String(255), nullable=True)
    banner_images = Column(JSON, nullable=True)
    featured_achievements = Column(JSON, nullable=True)
    featured_members = Column(JSON, nullable=True)


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
