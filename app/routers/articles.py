from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.dependencies.auth import (
    get_db,
    require_elite_member,
    require_admin,
    get_current_user,
    require_member,
    get_current_user_from_cookie,
)
from app.models import Article, ArticleTag, ArticleStatus, User, UserRole, GuideVote
from app.schemas import (
    ArticleCreate,
    ArticleUpdate,
    ArticleOut,
    ArticleListItem,
    ArticleListResponse,
)
from app.utils.sanitize import sanitize_html

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("", response_model=List[ArticleListItem])
def list_articles(
    page: int = 1,
    page_size: int = 10,
    featured: Optional[int] = 0,
    db: Session = Depends(get_db),
):
    query = db.query(Article).filter(Article.status == ArticleStatus.PUBLISHED)

    if featured:
        query = query.filter(Article.is_featured == True)

    query = query.order_by(Article.created_at.desc())
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    result: List[ArticleListItem] = []
    for a in items:
        tags = [t.tag_name for t in a.tags]
        excerpt = (a.content[:120] + "...") if len(a.content) > 120 else a.content
        result.append(
            ArticleListItem(
                id=a.id,
                title=a.title,
                excerpt=excerpt,
                author_nickname=a.author.nickname,
                created_at=a.created_at,
                tags=tags,
            )
        )
    return result


@router.get("/paged", response_model=ArticleListResponse)
def list_articles_paged(
    page: int = 1,
    page_size: int = 10,
    featured: Optional[int] = 0,
    search: Optional[str] = None,
    category: Optional[str] = None,
    tag: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_from_cookie),
):
    """攻略列表（带总数 & 筛选），用于前端分页/筛选 UI。"""

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10
    if page_size > 50:
        page_size = 50

    q = db.query(Article).filter(Article.status == ArticleStatus.PUBLISHED)

    if featured:
        q = q.filter(Article.is_featured == True)

    if category:
        q = q.filter(Article.category == category)

    if search:
        like = f"%{search}%"
        q = q.filter(or_(Article.title.ilike(like), Article.content.ilike(like)))

    if tag:
        q = q.join(ArticleTag).filter(ArticleTag.tag_name == tag)

    # total：SQL Server 需要 ORDER BY 列出现在 SELECT 中，改用 group_by + 子查询计数
    id_query = (
        q.with_entities(Article.id, Article.created_at)
        .group_by(Article.id, Article.created_at)
    )

    total = db.query(func.count()).select_from(id_query.subquery()).scalar() or 0

    # 分页拿到 id 列表，再查实体
    id_rows = (
        id_query.order_by(Article.created_at.desc(), Article.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    ids = [r[0] for r in id_rows]

    items = []
    if ids:
        items = (
            db.query(Article)
            .filter(Article.id.in_(ids))
            .order_by(Article.created_at.desc(), Article.id.desc())
            .all()
        )

    vote_map: dict[int, int] = {}
    if current_user and ids:
        rows = (
            db.query(GuideVote.article_id, GuideVote.action_type)
            .filter(
                GuideVote.user_id == current_user.id,
                GuideVote.article_id.in_(ids),
            )
            .all()
        )
        vote_map = {aid: act for aid, act in rows}

    result: List[ArticleListItem] = []
    for a in items:
        tags = [t.tag_name for t in a.tags]
        excerpt = (a.content[:120] + "...") if len(a.content) > 120 else a.content
        current_action = None
        if a.id in vote_map:
            current_action = "up" if vote_map[a.id] == 1 else "down"
        result.append(
            ArticleListItem(
                id=a.id,
                title=a.title,
                excerpt=excerpt,
                author_nickname=a.author.nickname,
                created_at=a.created_at,
                tags=tags,
                upvote_count=int(getattr(a, "upvote_count", 0) or 0),
                downvote_count=int(getattr(a, "downvote_count", 0) or 0),
                current_user_action=current_action,
            )
        )

    return ArticleListResponse(
        items=result,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{article_id}", response_model=ArticleOut)
def get_article(article_id: int, db: Session = Depends(get_db)):
    article = (
        db.query(Article)
        .filter(
            Article.id == article_id, Article.status != ArticleStatus.DELETED
        )
        .first()
    )
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="文章不存在"
        )

    return ArticleOut(
        id=article.id,
        title=article.title,
        content=article.content,
        author_id=article.author_id,
        author_nickname=article.author.nickname,
        created_at=article.created_at,
        updated_at=article.updated_at,
        status=article.status,
        category=article.category,
        is_featured=article.is_featured,
        upvote_count=int(getattr(article, "upvote_count", 0) or 0),
        downvote_count=int(getattr(article, "downvote_count", 0) or 0),
        tags=[
            {"id": t.id, "tag_name": t.tag_name}
            for t in article.tags
        ],
    )


@router.post("", response_model=ArticleOut)
def create_article(
    payload: ArticleCreate,
    current_user: User = Depends(require_member),
    db: Session = Depends(get_db),
):
    safe_html = sanitize_html(payload.content)

    article = Article(
        title=payload.title,
        content=safe_html,
        author_id=current_user.id,
        category=payload.category,
        status=ArticleStatus.PUBLISHED,
        is_featured=payload.is_featured or False,
    )
    db.add(article)
    db.flush()

    tags = []
    for tag_name in payload.tags or []:
        tag = ArticleTag(article_id=article.id, tag_name=tag_name)
        db.add(tag)
        tags.append(tag)

    # 发布攻略，影响力 +10
    if current_user.profile:
        current_user.profile.influence = (current_user.profile.influence or 0) + 10
    
    db.commit()
    db.refresh(article)

    return ArticleOut(
        id=article.id,
        title=article.title,
        content=article.content,
        author_id=article.author_id,
        author_nickname=article.author.nickname,
        created_at=article.created_at,
        updated_at=article.updated_at,
        status=article.status,
        category=article.category,
        is_featured=article.is_featured,
        upvote_count=int(getattr(article, "upvote_count", 0) or 0),
        downvote_count=int(getattr(article, "downvote_count", 0) or 0),
        tags=[{"id": t.id, "tag_name": t.tag_name} for t in article.tags],
    )


@router.put("/{article_id}", response_model=ArticleOut)
def update_article(
    article_id: int,
    payload: ArticleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(404, "文章不存在")

    is_admin = current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]
    if article.author_id != current_user.id and not is_admin:
        raise HTTPException(403, "仅作者或管理员可编辑")

    if payload.title is not None:
        article.title = payload.title
    if payload.content is not None:
        article.content = sanitize_html(payload.content)
    if payload.category is not None:
        article.category = payload.category
    if payload.status is not None:
        article.status = payload.status
    if payload.is_featured is not None:
        article.is_featured = payload.is_featured

    if payload.tags is not None:
        db.query(ArticleTag).filter(
            ArticleTag.article_id == article.id
        ).delete()
        for tag_name in payload.tags:
            db.add(ArticleTag(article_id=article.id, tag_name=tag_name))

    db.commit()
    db.refresh(article)

    return ArticleOut(
        id=article.id,
        title=article.title,
        content=article.content,
        author_id=article.author_id,
        author_nickname=article.author.nickname,
        created_at=article.created_at,
        updated_at=article.updated_at,
        status=article.status,
        category=article.category,
        is_featured=article.is_featured,
        upvote_count=int(getattr(article, "upvote_count", 0) or 0),
        downvote_count=int(getattr(article, "downvote_count", 0) or 0),
        tags=[{"id": t.id, "tag_name": t.tag_name} for t in article.tags],
    )


@router.delete("/{article_id}")
def delete_article(
    article_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(404, "文章不存在")
    article.status = ArticleStatus.DELETED
    db.commit()
    return {"message": "删除成功"}
