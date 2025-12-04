from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db, require_elite_member, require_admin, get_current_user
from app.models import Article, ArticleTag, ArticleStatus, User
from app.schemas import (
    ArticleCreate,
    ArticleUpdate,
    ArticleOut,
    ArticleListItem,
)

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
        tags=[
            {"id": t.id, "tag_name": t.tag_name}
            for t in article.tags
        ],
    )


@router.post("", response_model=ArticleOut)
def create_article(
    payload: ArticleCreate,
    current_user: User = Depends(require_elite_member),
    db: Session = Depends(get_db),
):
    article = Article(
        title=payload.title,
        content=payload.content,
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

    is_admin = current_user.role == current_user.role.ADMIN
    if article.author_id != current_user.id and not is_admin:
        raise HTTPException(403, "仅作者或管理员可编辑")

    if payload.title is not None:
        article.title = payload.title
    if payload.content is not None:
        article.content = payload.content
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
