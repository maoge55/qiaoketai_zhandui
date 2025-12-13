from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, EmailStr

from app.models import UserRole, ArticleStatus


# 通用
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int
    username: str
    role: UserRole


# 用户 & 认证
class UserBase(BaseModel):
    id: int
    username: str
    nickname: str
    email: EmailStr
    role: UserRole

    class Config:
        from_attributes = True


class UserRegister(BaseModel):
    username: str
    nickname: str
    email: EmailStr
    password_md5: str
    verification_code: str


class UserLogin(BaseModel):
    username_or_email: str
    password_md5: str


class UserProfileBase(BaseModel):
    avatar_url: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    strength_score: Optional[str] = None
    bio: Optional[str] = None
    avg_arena_wins: Optional[float] = None
    arena_best_rank: Optional[str] = None
    other_tags: Optional[str] = None
    # ✅ 新增：影响力 + 当前赛季排名（只读用）
    influence: int | None = None
    current_season_rank: int | None = None

    class Config:
        from_attributes = True


class UserProfileOut(UserProfileBase):
    user_id: int
    user: Optional[UserBase] = None


class UserProfileUpdate(UserProfileBase):
    nickname: Optional[str] = None

class UserProfileAdminUpdate(BaseModel):
    influence: int | None = None
    current_season_rank: int | None = None


class SendVerificationCodeRequest(BaseModel):
    email: EmailStr


# 文章 & 评论
class ArticleTagOut(BaseModel):
    id: int
    tag_name: str

    class Config:
        from_attributes = True


class ArticleBase(BaseModel):
    title: str
    content: str
    category: Optional[str] = None
    is_featured: Optional[bool] = False


class ArticleCreate(ArticleBase):
    tags: Optional[List[str]] = []


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    status: Optional[ArticleStatus] = None
    is_featured: Optional[bool] = None
    tags: Optional[List[str]] = None


class ArticleOut(BaseModel):
    id: int
    title: str
    content: str
    author_id: int
    author_nickname: str
    created_at: datetime
    updated_at: datetime
    status: ArticleStatus
    category: Optional[str]
    is_featured: bool
    tags: List[ArticleTagOut]

    class Config:
        from_attributes = True


class ArticleListItem(BaseModel):
    id: int
    title: str
    excerpt: str
    author_nickname: str
    created_at: datetime
    tags: List[str]

    class Config:
        from_attributes = True


class ArticleListResponse(BaseModel):
    items: List[ArticleListItem]
    page: int
    page_size: int
    total: int


class CommentCreate(BaseModel):
    content: str


class CommentReplyCreate(BaseModel):
    content: str


class CommentOut(BaseModel):
    id: int
    article_id: int
    user_id: int
    user_nickname: str
    parent_id: Optional[int]
    content: str
    created_at: datetime
    is_pinned: bool = False

    class Config:
        from_attributes = True


# 卡牌
class CardOut(BaseModel):
    id: int
    name: str
    expansion: str
    mana_cost: int
    card_class: str
    rarity: str
    version: Optional[str]
    pic: Optional[str]
    description: Optional[str]
    arena_score: Optional[int]
    arena_win_rates: Any = None
    short_review: Optional[str]
    reviewer_nickname: Optional[str] = None
    average_score: float | None = None
    class Config:
        from_attributes = True


class CardReviewUpsert(BaseModel):
    score: float
    content: str
    game_version: Optional[str] = None


class CardReviewMineOut(BaseModel):
    review_id: int
    score: float
    content: str
    created_at: datetime
    game_version: Optional[str] = None

    class Config:
        from_attributes = True

# 现有的 CardOut 下面追加

class CardReviewCardInfo(BaseModel):
    """卡牌信息（用于卡牌详情 + 点评页头部）"""
    id: int
    name: str
    image_url: Optional[str] = None
    average_score: Optional[float] = None
    card_class: Optional[str] = None

    class Config:
        from_attributes = True


class CardReviewReviewer(BaseModel):
    id: int
    name: str
    is_expert: bool = False


class CardReviewItem(BaseModel):
    review_id: int
    reviewer: CardReviewReviewer
    score: float
    content: str
    created_at: datetime
    game_version: Optional[str] = None

    class Config:
        from_attributes = True


class Pagination(BaseModel):
    page: int
    total: int


class CardReviewsResponse(BaseModel):
    card_info: CardReviewCardInfo
    reviews: List[CardReviewItem]
    pagination: Pagination



# 成就
class AchievementOut(BaseModel):
    id: int
    member_id: int
    member_nickname: str
    title: str
    description: Optional[str]
    season_or_version: Optional[str]
    rank_or_result: Optional[str]
    achieved_at: Optional[datetime]

    class Config:
        from_attributes = True


# 首页配置
class HomepageConfigOut(BaseModel):
    id: int
    team_logo_url: Optional[str]
    banner_images: Optional[dict]
    featured_achievements: Optional[dict]
    featured_members: Optional[dict]

    class Config:
        from_attributes = True


class HomepageConfigUpdate(BaseModel):
    team_logo_url: Optional[str] = None
    banner_images: Optional[dict] = None
    featured_achievements: Optional[dict] = None
    featured_members: Optional[dict] = None


class UserRegister(BaseModel):
    username: str
    nickname: str
    email: EmailStr
    password_md5: str
    verification_code: str
    # 新增：会员码（前端传 md5）
    membership_code_md5: str | None = None
