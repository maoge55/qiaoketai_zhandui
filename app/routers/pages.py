from fastapi import APIRouter, Depends, Request,HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import case

from app.dependencies.auth import get_db, get_current_user_from_cookie
from app.models import (
    Article,
    ArticleStatus,
    Achievement,
    AchievementStatus,
    Card,
    HomepageConfig,
    User,
    UserProfile,
    UserRole,
)
import re

templates = Jinja2Templates(directory="app/templates")

# 自定义过滤器：去除 HTML 标签
def strip_tags(value):
    """去除 HTML 标签，只保留纯文本"""
    if not value:
        return ""
    # 去除 HTML 标签
    clean = re.sub(r'<[^>]+>', '', str(value))
    # 去除多余空白
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

templates.env.filters['strip_tags'] = strip_tags

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_cookie),
):
    homepage_config = db.query(HomepageConfig).first()
    if homepage_config:
        homepage_config.banner_images = homepage_config.banner_images or []
        homepage_config.featured_achievements = (
            homepage_config.featured_achievements or []
        )
        homepage_config.featured_members = homepage_config.featured_members or []

    featured_member_profiles = []
    if homepage_config and homepage_config.featured_members:
        seen_ids = set()
        for token in homepage_config.featured_members:
            email_like = f"%{token}%"
            profile = (
                db.query(UserProfile)
                .join(UserProfile.user)
                .filter(User.email.ilike(email_like))
                .first()
            )
            if profile and profile.id not in seen_ids:
                featured_member_profiles.append(profile)
                seen_ids.add(profile.id)

    # 精选文章 + 成就 + 高分大神
    featured_articles = (
        db.query(Article)
        .filter(
            Article.status == ArticleStatus.PUBLISHED,
            Article.is_featured == True,
        )
        .order_by(Article.created_at.desc())
        .limit(5)
        .all()
    )

    achievements = (
        db.query(Achievement)
        .filter(Achievement.status == AchievementStatus.ACTIVE)
        .order_by(Achievement.is_pinned.desc(), Achievement.achieved_at.desc())
        .limit(6)
        .all()
    )

    # 首页榜单：只展示前三名
    # 排序：优先按当前赛季排名（asc），没有排名的按影响力（desc）
    # SQL Server NULLS LAST 模拟
    rank_is_null = case(
        (UserProfile.current_season_rank.is_(None), 1),
        else_=0,
    )
    
    top_members = (
        db.query(UserProfile)
        .join(UserProfile.user)
        .order_by(
            rank_is_null,
            UserProfile.current_season_rank.asc(),
            UserProfile.influence.desc(),
        )
        .limit(3)
        .all()
    )

    featured_achievements_text = (
        homepage_config.featured_achievements if homepage_config else []
    )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "current_user": current_user,
            "featured_articles": featured_articles,
            "achievements": achievements,
            "top_members": top_members,
            "homepage_config": homepage_config,
            "featured_member_profiles": featured_member_profiles,
            "featured_achievements_text": featured_achievements_text,
        },
    )


@router.get("/guides", response_class=HTMLResponse)
async def guides_page(
    request: Request,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_cookie),
):
    query = (
        db.query(Article)
        .filter(Article.status == ArticleStatus.PUBLISHED)
        .order_by(Article.created_at.desc())
    )
    articles = query.offset((page - 1) * page_size).limit(page_size).all()

    return templates.TemplateResponse(
        "guides.html",
        {
            "request": request,
            "current_user": current_user,
            "articles": articles,
            "page": page,
        },
    )


@router.get("/cards", response_class=HTMLResponse)
async def cards_page(
    request: Request,
    current_user=Depends(get_current_user_from_cookie),
):
    return templates.TemplateResponse(
        "cards.html",
        {"request": request, "current_user": current_user},
    )

@router.get("/cards/{card_id}", response_class=HTMLResponse)
async def card_detail_page(
    card_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_cookie),
):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="卡牌不存在")

    return templates.TemplateResponse(
        "card_detail.html",
        {
            "request": request,
            "card": card,
            "current_user": current_user,  # 跟其他页面保持一致
            "user": current_user,          # 可要可不要，看模板里用哪个
        },
    )

@router.get("/legends", response_class=HTMLResponse)
async def legends_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_cookie),
):
    achievements = (
        db.query(Achievement)
        .filter(Achievement.status == AchievementStatus.ACTIVE)
        .order_by(Achievement.is_pinned.desc(), Achievement.achieved_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "legends.html",
        {
            "request": request,
            "current_user": current_user,
            "achievements": achievements,
        },
    )


@router.get("/members", response_class=HTMLResponse)
async def members_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_cookie),
):
    members = db.query(UserProfile).all()
    return templates.TemplateResponse(
        "members.html",
        {
            "request": request,
            "current_user": current_user,
            "members": members,
        },
    )


@router.get("/ua-rank", response_class=HTMLResponse)
async def ua_rank_page(
    request: Request,
    current_user=Depends(get_current_user_from_cookie),
):
    """地下竞技场国服榜单 - 敲可爱战队500强"""
    return templates.TemplateResponse(
        "ua_rank.html",
        {
            "request": request,
            "current_user": current_user,
        },
    )


@router.get("/members/{user_id}", response_class=HTMLResponse)
async def member_detail_page(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_cookie),
):
    user = db.query(User).filter(User.id == user_id).first()
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    achievements = (
        db.query(Achievement)
        .filter(
            Achievement.member_id == user_id,
            Achievement.status == AchievementStatus.ACTIVE,
        )
        .order_by(Achievement.is_pinned.desc(), Achievement.achieved_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "member_detail.html",
        {
            "request": request,
            "current_user": current_user,
            "user": user,
            "profile": profile,
            "achievements": achievements,
        },
    )


@router.get("/join", response_class=HTMLResponse)
async def join_page(
    request: Request, current_user=Depends(get_current_user_from_cookie)
):
    return templates.TemplateResponse(
        "join.html",
        {"request": request, "current_user": current_user},
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request, current_user=Depends(get_current_user_from_cookie)
):
    if current_user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "current_user": current_user},
    )


@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request, current_user=Depends(get_current_user_from_cookie)
):
    if current_user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "current_user": current_user},
    )


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request, current_user=Depends(get_current_user_from_cookie)
):
    if not current_user or current_user.role not in [
        UserRole.MEMBER,
        UserRole.ELITE_MEMBER,
        UserRole.ADMIN,
        UserRole.SUPER_ADMIN,
    ]:
        return templates.TemplateResponse(
            "error_403.html",
            {
                "request": request,
                "message": "仅战队成员可访问",
                "current_user": current_user,
            },
            status_code=403,
        )
    return templates.TemplateResponse(
        "profile_edit.html",
        {"request": request, "current_user": current_user},
    )


@router.get("/guides/new", response_class=HTMLResponse)
async def new_guide_page(
    request: Request, current_user=Depends(get_current_user_from_cookie)
):
    if not current_user or current_user.role not in [
        UserRole.ELITE_MEMBER,
        UserRole.ADMIN,
        UserRole.SUPER_ADMIN,
    ]:
        return templates.TemplateResponse(
            "error_403.html",
            {
                "request": request,
                "message": "仅大神成员可以发布攻略",
                "current_user": current_user,
            },
            status_code=403,
        )
    return templates.TemplateResponse(
        "guide_new.html",
        {"request": request, "current_user": current_user},
    )


@router.get("/guides/{article_id}", response_class=HTMLResponse)
async def guide_detail_page(
    article_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_cookie),
):
    """Detail page must come after /guides/new to avoid path param capturing 'new'."""
    article = (
        db.query(Article)
        .filter(
            Article.id == article_id, Article.status != ArticleStatus.DELETED
        )
        .first()
    )
    if not article:
        return templates.TemplateResponse(
            "error_403.html",
            {
                "request": request,
                "message": "文章不存在",
                "current_user": current_user,
            },
        )
    return templates.TemplateResponse(
        "guide_detail.html",
        {
            "request": request,
            "current_user": current_user,
            "article": article,
        },
    )


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(
    request: Request, current_user=Depends(get_current_user_from_cookie)
):
    if not current_user or current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        return templates.TemplateResponse(
            "error_403.html",
            {
                "request": request,
                "message": "管理员专用入口",
                "current_user": current_user,
            },
            status_code=403,
        )
    return templates.TemplateResponse(
        "admin_articles.html",
        {"request": request, "current_user": current_user},
    )


@router.get("/admin/achievements", response_class=HTMLResponse)
async def admin_achievements_page(
    request: Request, current_user=Depends(get_current_user_from_cookie)
):
    if not current_user or current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        return templates.TemplateResponse(
            "error_403.html",
            {
                "request": request,
                "message": "管理员专用入口",
                "current_user": current_user,
            },
            status_code=403,
        )
    return templates.TemplateResponse(
        "admin_achievements.html",
        {"request": request, "current_user": current_user},
    )

@router.get("/admin/members", response_class=HTMLResponse)
async def admin_members_page(
    request: Request, current_user=Depends(get_current_user_from_cookie)
):
    if not current_user or current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        return templates.TemplateResponse(
            "error_403.html",
            {
                "request": request,
                "message": "管理员专用入口",
                "current_user": current_user,
            },
            status_code=403,
        )
    return templates.TemplateResponse(
        "admin_members.html",
        {"request": request, "current_user": current_user},
    )


@router.get("/admin/homepage", response_class=HTMLResponse)
async def admin_homepage_page(
    request: Request, current_user=Depends(get_current_user_from_cookie)
):
    if not current_user or current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        return templates.TemplateResponse(
            "error_403.html",
            {
                "request": request,
                "message": "管理员专用入口",
                "current_user": current_user,
            },
            status_code=403,
        )
    return templates.TemplateResponse(
        "admin_homepage.html",
        {"request": request, "current_user": current_user},
    )


@router.get("/admin/achievements/new", response_class=HTMLResponse)
async def admin_achievement_new_page(
    request: Request, current_user=Depends(get_current_user_from_cookie)
):
    if not current_user or current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        return templates.TemplateResponse(
            "error_403.html",
            {
                "request": request,
                "message": "管理员专用入口",
                "current_user": current_user,
            },
            status_code=403,
        )
    return templates.TemplateResponse(
        "admin_achievement_edit.html",
        {
            "request": request,
            "current_user": current_user,
            "achievement_id": None,
        },
    )


@router.get("/admin/achievements/{achievement_id}/edit", response_class=HTMLResponse)
async def admin_achievement_edit_page(
    achievement_id: int,
    request: Request,
    current_user=Depends(get_current_user_from_cookie),
):
    if not current_user or current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        return templates.TemplateResponse(
            "error_403.html",
            {
                "request": request,
                "message": "管理员专用入口",
                "current_user": current_user,
            },
            status_code=403,
        )
    return templates.TemplateResponse(
        "admin_achievement_edit.html",
        {
            "request": request,
            "current_user": current_user,
            "achievement_id": achievement_id,
        },
    )


@router.get("/admin/arena-pool", response_class=HTMLResponse)
async def admin_arena_pool_page(
    request: Request, current_user=Depends(get_current_user_from_cookie)
):
    if not current_user or current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        return templates.TemplateResponse(
            "error_403.html",
            {
                "request": request,
                "message": "管理员专用入口",
                "current_user": current_user,
            },
            status_code=403,
        )
    return templates.TemplateResponse(
        "admin_arena_pool.html",
        {"request": request, "current_user": current_user},
    )
