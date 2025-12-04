from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db, get_current_user
from app.models import Comment, Article
from app.schemas import CommentCreate, CommentReplyCreate, CommentOut

router = APIRouter(prefix="/api", tags=["comments"])


@router.get("/articles/{article_id}/comments", response_model=List[CommentOut])
def list_comments(article_id: int, db: Session = Depends(get_db)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(404, "文章不存在")

    comments = (
        db.query(Comment)
        .filter(Comment.article_id == article_id)
        .order_by(Comment.created_at.asc())
        .all()
    )

    result = []
    for c in comments:
        result.append(
            CommentOut(
                id=c.id,
                article_id=c.article_id,
                user_id=c.user_id,
                user_nickname=c.user.nickname,
                parent_id=c.parent_id,
                content=c.content,
                created_at=c.created_at,
            )
        )
    return result


@router.post("/articles/{article_id}/comments", response_model=CommentOut)
def create_comment(
    article_id: int,
    payload: CommentCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(404, "文章不存在")

    comment = Comment(
        article_id=article_id,
        user_id=current_user.id,
        content=payload.content,
        parent_id=None,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return CommentOut(
        id=comment.id,
        article_id=comment.article_id,
        user_id=comment.user_id,
        user_nickname=current_user.nickname,
        parent_id=comment.parent_id,
        content=comment.content,
        created_at=comment.created_at,
    )


@router.post("/comments/{comment_id}/reply", response_model=CommentOut)
def reply_comment(
    comment_id: int,
    payload: CommentReplyCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parent = db.query(Comment).filter(Comment.id == comment_id).first()
    if not parent:
        raise HTTPException(404, "评论不存在")

    reply = Comment(
        article_id=parent.article_id,
        user_id=current_user.id,
        parent_id=parent.id,
        content=payload.content,
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)

    return CommentOut(
        id=reply.id,
        article_id=reply.article_id,
        user_id=reply.user_id,
        user_nickname=current_user.nickname,
        parent_id=reply.parent_id,
        content=reply.content,
        created_at=reply.created_at,
    )
