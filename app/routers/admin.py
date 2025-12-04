from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db, require_admin
from app.models import User, Article, HomepageConfig, UserRole, ArticleStatus
from app.schemas import HomepageConfigUpdate, HomepageConfigOut

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users")
def admin_list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "nickname": u.nickname,
            "email": u.email,
            "role": u.role.value,
        }
        for u in users
    ]


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
