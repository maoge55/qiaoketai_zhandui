from typing import List

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db, get_current_user
from app.models import Comment, Article, UserRole
from app.schemas import CommentCreate, CommentReplyCreate, CommentOut

router = APIRouter(prefix="/api", tags=["comments"])


@router.get("/articles/{article_id}/comments", response_model=List[CommentOut])
def list_comments(article_id: int, db: Session = Depends(get_db)):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(404, "文章不存在")

    # SQL Server 不支持 NULLS LAST，这里依赖 pinned_at DESC 的默认 NULL 排序即可
    comments = (
        db.query(Comment)
        .filter(Comment.article_id == article_id)
        .order_by(Comment.is_pinned.desc(), Comment.pinned_at.desc(), Comment.created_at.asc())
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
                is_pinned=bool(getattr(c, "is_pinned", False)),
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
        is_pinned=bool(getattr(comment, "is_pinned", False)),
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
        is_pinned=bool(getattr(reply, "is_pinned", False)),
    )


def _delete_comment_tree(db: Session, comment: Comment) -> None:
    """递归删除评论（含所有回复），避免 self FK 导致的删除失败。"""

    children = db.query(Comment).filter(Comment.parent_id == comment.id).all()
    for child in children:
        _delete_comment_tree(db, child)
    db.delete(comment)


@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除评论（作者/文章作者/管理员）。"""

    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(404, "评论不存在")

    article = db.query(Article).filter(Article.id == comment.article_id).first()
    if not article:
        raise HTTPException(404, "文章不存在")

    is_admin = current_user.role == UserRole.ADMIN
    is_owner = comment.user_id == current_user.id
    is_article_author = article.author_id == current_user.id
    if not (is_admin or is_owner or is_article_author):
        raise HTTPException(403, "权限不足")

    _delete_comment_tree(db, comment)
    db.commit()
    return {"message": "删除成功"}


@router.post("/comments/{comment_id}/pin")
def pin_comment(
    comment_id: int,
    payload: dict,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """置顶/取消置顶（文章作者或管理员）。

    payload: {"pinned": true/false}
    """

    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(404, "评论不存在")

    if comment.parent_id is not None:
        raise HTTPException(400, "仅支持置顶一级评论")

    article = db.query(Article).filter(Article.id == comment.article_id).first()
    if not article:
        raise HTTPException(404, "文章不存在")

    is_admin = current_user.role == UserRole.ADMIN
    is_article_author = article.author_id == current_user.id
    if not (is_admin or is_article_author):
        raise HTTPException(403, "权限不足")

    pinned = bool(payload.get("pinned", True))
    comment.is_pinned = pinned
    comment.pinned_at = datetime.utcnow() if pinned else None
    db.commit()
    return {"message": "ok", "is_pinned": comment.is_pinned}
