from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db, require_admin
from app.models import User, Article, HomepageConfig, UserRole, ArticleStatus, UserProfile
from app.schemas import (
    HomepageConfigUpdate,
    HomepageConfigOut,
    UserProfileAdminUpdate,
)


router = APIRouter(prefix="/api/admin", tags=["admin"])


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


@router.get("/homepage", response_model=HomepageConfigOut)
def admin_get_homepage(
    _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    config = db.query(HomepageConfig).first()
    if not config:
        config = HomepageConfig(
            team_logo_url="/static/img/logo.png",
            banner_images=[],
            featured_achievements={},
            featured_members={},
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


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
    return config
