from typing import List, Optional
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db, require_admin
from app.models import (
    User,
    Article,
    HomepageConfig,
    UserRole,
    ArticleStatus,
    UserProfile,
    Achievement,
    AchievementStatus,
)
from app.schemas import (
    HomepageConfigUpdate,
    HomepageConfigOut,
    UserProfileAdminUpdate,
    AchievementAdminCreate,
    AchievementAdminUpdate,
)

# Static upload targets for homepage assets
BASE_DIR = Path(__file__).resolve().parent.parent
HOMEPAGE_UPLOAD_DIR = BASE_DIR / "static" / "uploads" / "homepage"
HOMEPAGE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
HOMEPAGE_LOGO_PATH = HOMEPAGE_UPLOAD_DIR / "team_logo.png"
HOMEPAGE_BANNER_PATH = HOMEPAGE_UPLOAD_DIR / "banner.png"


router = APIRouter(prefix="/api/admin", tags=["admin"])


def _normalize_homepage_config(config: HomepageConfig) -> HomepageConfig:
    """Ensure JSON fields are always lists to satisfy schema and frontend expectations."""

    def to_list(val):
        if val is None:
            return []
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            return list(val.values())
        if isinstance(val, (str, int, float, bool)):
            return [val]
        return []

    config.banner_images = to_list(config.banner_images)
    config.featured_achievements = to_list(config.featured_achievements)
    config.featured_members = to_list(config.featured_members)
    return config


def _achievement_to_dict(a: Achievement, user: Optional[User] = None):
    """Serialize achievement with member info for admin responses."""

    return {
        "id": a.id,
        "member_id": a.member_id,
        "member_nickname": (user.nickname if user else None),
        "member_email": (user.email if user else None),
        "title": a.title,
        "description": a.description,
        "season_or_version": a.season_or_version,
        "rank_or_result": a.rank_or_result,
        "achieved_at": a.achieved_at,
        "status": a.status.value if hasattr(a, "status") else None,
        "is_pinned": bool(getattr(a, "is_pinned", False)),
    }


def _validate_image(file: UploadFile, max_size: int = 5 * 1024 * 1024) -> bytes:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图片上传")
    data = file.file.read()
    if len(data) > max_size:
        raise HTTPException(status_code=400, detail="图片不能超过 5MB")
    return data


@router.get("/users")
def admin_list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    """兼容旧接口：返回全部用户。

    同时补充 profile 的 influence/current_season_rank，方便后台成员页直接使用。
    """

    rows = (
        db.query(User, UserProfile)
        .outerjoin(UserProfile, UserProfile.user_id == User.id)
        .order_by(User.id.asc())
        .all()
    )

    result = []
    for u, p in rows:
        result.append(
            {
                "id": u.id,
                "username": u.username,
                "nickname": u.nickname,
                "email": u.email,
                "role": u.role.value,
                "influence": p.influence if p else None,
                "current_season_rank": p.current_season_rank if p else None,
            }
        )
    return result


@router.get("/users/paged")
def admin_list_users_paged(
    page: int = 1,
    page_size: int = 25,
    search: Optional[str] = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """后台成员列表分页接口（异步加载用）。"""

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 25
    if page_size > 100:
        page_size = 100

    q = db.query(User).order_by(User.id.asc())
    if search:
        like = f"%{search}%"
        q = q.filter(
            (User.username.ilike(like))
            | (User.nickname.ilike(like))
            | (User.email.ilike(like))
        )

    total = q.count()
    users = q.offset((page - 1) * page_size).limit(page_size).all()

    # profile 批量查询
    user_ids = [u.id for u in users]
    profiles = (
        db.query(UserProfile)
        .filter(UserProfile.user_id.in_(user_ids))
        .all()
    )
    prof_map = {p.user_id: p for p in profiles}

    items = []
    for u in users:
        p = prof_map.get(u.id)
        items.append(
            {
                "id": u.id,
                "username": u.username,
                "nickname": u.nickname,
                "email": u.email,
                "role": u.role.value,
                "influence": p.influence if p else None,
                "current_season_rank": p.current_season_rank if p else None,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.put("/users/{user_id}")
def admin_update_user(
    user_id: int,
    payload: dict,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")

    role = payload.get("role")
    if role:
        user.role = UserRole(role)
    db.commit()
    return {"message": "更新成功"}

@router.put("/members/{user_id}/profile_admin")
def admin_update_member_profile(
    user_id: int,
    payload: UserProfileAdminUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # 确保用户存在
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 找到或创建 profile
    profile = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == user_id)
        .first()
    )
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)

    # 只有管理员通过这个接口才能改影响力和当前赛季排名
    if payload.influence is not None:
        profile.influence = payload.influence
    if payload.current_season_rank is not None:
        profile.current_season_rank = payload.current_season_rank

    db.commit()
    db.refresh(profile)
    return profile


@router.get("/articles")
def admin_list_articles(
    _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    articles = db.query(Article).all()
    return [
        {
            "id": a.id,
            "title": a.title,
            "author": a.author.nickname,
            "status": a.status.value,
            "created_at": a.created_at,
            "is_featured": bool(a.is_featured),
        }
        for a in articles
    ]


@router.put("/articles/{article_id}")
def admin_update_article(
    article_id: int,
    payload: dict,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(404, "文章不存在")
    status_val = payload.get("status")
    if status_val:
        article.status = ArticleStatus(status_val)
    if "is_featured" in payload:
        article.is_featured = bool(payload.get("is_featured"))
    db.commit()
    return {"message": "更新成功"}


@router.delete("/articles/{article_id}")
def admin_delete_article(
    article_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(404, "文章不存在")
    article.status = ArticleStatus.DELETED
    db.commit()
    return {"message": "删除成功"}


@router.get("/achievements")
def admin_list_achievements(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    status: Optional[str] = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """分页列出成就。默认排除 deleted；支持标题/成员昵称/邮箱搜索。"""

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 200:
        page_size = 200

    q = db.query(Achievement, User).join(User, User.id == Achievement.member_id)

    if status:
        try:
            q = q.filter(Achievement.status == AchievementStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的状态")
    else:
        q = q.filter(Achievement.status != AchievementStatus.DELETED)

    if search:
        like = f"%{search}%"
        q = q.filter(
            or_(
                Achievement.title.ilike(like),
                User.nickname.ilike(like),
                User.email.ilike(like),
            )
        )

    total = q.count()
    rows = (
        q.order_by(
            Achievement.is_pinned.desc(),
            Achievement.achieved_at.desc(),
            Achievement.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [_achievement_to_dict(a, u) for a, u in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/achievements")
def admin_create_achievement(
    payload: AchievementAdminCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    member = db.query(User).filter(User.id == payload.member_id).first()
    if not member:
        raise HTTPException(404, "成员不存在")

    achievement = Achievement(
        member_id=payload.member_id,
        title=payload.title,
        description=payload.description,
        season_or_version=payload.season_or_version,
        rank_or_result=payload.rank_or_result,
        achieved_at=payload.achieved_at,
        status=payload.status,
        is_pinned=payload.is_pinned,
    )
    db.add(achievement)
    db.commit()
    db.refresh(achievement)
    return _achievement_to_dict(achievement, member)


@router.get("/achievements/{achievement_id}")
def admin_get_achievement(
    achievement_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    achievement = (
        db.query(Achievement, User)
        .join(User, User.id == Achievement.member_id)
        .filter(Achievement.id == achievement_id)
        .first()
    )
    if not achievement:
        raise HTTPException(404, "成就不存在")
    a, u = achievement
    return _achievement_to_dict(a, u)


@router.put("/achievements/{achievement_id}")
def admin_update_achievement(
    achievement_id: int,
    payload: AchievementAdminUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if not achievement:
        raise HTTPException(404, "成就不存在")

    if payload.member_id is not None:
        member = db.query(User).filter(User.id == payload.member_id).first()
        if not member:
            raise HTTPException(404, "成员不存在")
        achievement.member_id = payload.member_id

    if payload.title is not None:
        achievement.title = payload.title
    if payload.description is not None:
        achievement.description = payload.description
    if payload.season_or_version is not None:
        achievement.season_or_version = payload.season_or_version
    if payload.rank_or_result is not None:
        achievement.rank_or_result = payload.rank_or_result
    if payload.achieved_at is not None:
        achievement.achieved_at = payload.achieved_at
    if payload.status is not None:
        achievement.status = payload.status
    if payload.is_pinned is not None:
        achievement.is_pinned = bool(payload.is_pinned)

    db.commit()
    db.refresh(achievement)
    user = db.query(User).filter(User.id == achievement.member_id).first()
    return _achievement_to_dict(achievement, user)


@router.delete("/achievements/{achievement_id}")
def admin_delete_achievement(
    achievement_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if not achievement:
        raise HTTPException(404, "成就不存在")

    achievement.status = AchievementStatus.DELETED
    db.commit()
    return {"message": "删除成功"}


@router.get("/homepage", response_model=HomepageConfigOut)
def admin_get_homepage(
    _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    config = db.query(HomepageConfig).first()
    if not config:
        config = HomepageConfig(
            team_logo_url="/static/img/logo.png",
            banner_images=[],
            featured_achievements=[],
            featured_members=[],
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return _normalize_homepage_config(config)


@router.put("/homepage", response_model=HomepageConfigOut)
def admin_update_homepage(
    payload: HomepageConfigUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    config = db.query(HomepageConfig).first()
    if not config:
        config = HomepageConfig()
        db.add(config)

    if payload.team_logo_url is not None:
        config.team_logo_url = payload.team_logo_url
    if payload.banner_images is not None:
        config.banner_images = payload.banner_images
    if payload.featured_achievements is not None:
        config.featured_achievements = payload.featured_achievements
    if payload.featured_members is not None:
        config.featured_members = payload.featured_members

    db.commit()
    db.refresh(config)
    return _normalize_homepage_config(config)


@router.post("/homepage/upload/logo")
def admin_upload_homepage_logo(
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
):
    data = _validate_image(file)
    HOMEPAGE_LOGO_PATH.write_bytes(data)
    return {"url": f"/static/uploads/homepage/{HOMEPAGE_LOGO_PATH.name}"}


@router.post("/homepage/upload/banner")
def admin_upload_homepage_banner(
    files: List[UploadFile] = File(...),
    _: User = Depends(require_admin),
):
    if not files:
        raise HTTPException(status_code=400, detail="未选择图片")

    urls: list[str] = []
    for f in files:
        data = _validate_image(f)
        ext = ".png"
        if f.filename and "." in f.filename:
            ext = f.filename.rsplit(".", 1)[-1].lower()
            ext = "." + ext
        filename = f"banner_{uuid4().hex}{ext}"
        path = HOMEPAGE_UPLOAD_DIR / filename
        path.write_bytes(data)
        urls.append(f"/static/uploads/homepage/{filename}")

    return {"urls": urls}
