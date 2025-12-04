from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db, get_current_user_from_cookie
from app.models import Article, ArticleStatus, UserProfile, Achievement, UserRole

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_cookie),
):
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
        .order_by(Achievement.achieved_at.desc())
        .limit(6)
        .all()
    )

    top_members = (
        db.query(UserProfile)
        .join(UserProfile.user)
        .filter(
            UserProfile.strength_score.isnot(None),
        )
        .limit(8)
        .all()
    )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "current_user": current_user,
            "featured_articles": featured_articles,
            "achievements": achievements,
            "top_members": top_members,
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


@router.get("/guides/{article_id}", response_class=HTMLResponse)
async def guide_detail_page(
    article_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_cookie),
):
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


@router.get("/cards", response_class=HTMLResponse)
async def cards_page(
    request: Request,
    current_user=Depends(get_current_user_from_cookie),
):
    return templates.TemplateResponse(
        "cards.html",
        {"request": request, "current_user": current_user},
    )


@router.get("/legends", response_class=HTMLResponse)
async def legends_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_cookie),
):
    achievements = (
        db.query(Achievement)
        .order_by(Achievement.achieved_at.desc())
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


@router.get("/members/{user_id}", response_class=HTMLResponse)
async def member_detail_page(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_cookie),
):
    from app.models import User

    user = db.query(User).filter(User.id == user_id).first()
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    achievements = (
        db.query(Achievement)
        .filter(Achievement.member_id == user_id)
        .order_by(Achievement.achieved_at.desc())
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


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(
    request: Request, current_user=Depends(get_current_user_from_cookie)
):
    if not current_user or current_user.role != UserRole.ADMIN:
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
