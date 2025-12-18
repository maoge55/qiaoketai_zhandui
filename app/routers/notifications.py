from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db, get_current_user_from_cookie_required
from app.models import Article, Notification, User
from app.schemas import NotificationItem, NotificationListResponse, UnreadCountResponse

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/unread_count", response_model=UnreadCountResponse)
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie_required),
):
    cnt = (
        db.query(func.count(Notification.id))
        .filter(
            Notification.receiver_id == current_user.id,
            Notification.is_read == False,
        )
        .scalar()
        or 0
    )
    return UnreadCountResponse(count=int(cnt))


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    unread_only: Optional[bool] = Query(False),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie_required),
):
    q = (
        db.query(Notification)
        .filter(Notification.receiver_id == current_user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
    )
    if unread_only:
        q = q.filter(Notification.is_read == False)

    rows = q.limit(limit).all()

    # 批量查文章标题与发送者昵称
    article_ids = {n.article_id for n in rows}
    sender_ids = {n.sender_id for n in rows}

    article_map: dict[int, str] = {}
    if article_ids:
        for a in db.query(Article).filter(Article.id.in_(list(article_ids))).all():
            article_map[a.id] = a.title

    sender_map: dict[int, str] = {}
    if sender_ids:
        for u in db.query(User).filter(User.id.in_(list(sender_ids))).all():
            sender_map[u.id] = u.nickname or u.username

    items = []
    for n in rows:
        items.append(
            NotificationItem(
                id=n.id,
                sender_id=n.sender_id,
                sender_nickname=sender_map.get(n.sender_id, ""),
                article_id=n.article_id,
                article_title=article_map.get(n.article_id, ""),
                comment_id=n.comment_id,
                is_read=bool(n.is_read),
                created_at=n.created_at,
            )
        )

    return NotificationListResponse(items=items)


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_cookie_required),
):
    n = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.receiver_id == current_user.id,
        )
        .first()
    )
    if not n:
        raise HTTPException(status_code=404, detail="消息不存在")

    if not n.is_read:
        n.is_read = True
        n.read_at = datetime.utcnow()
        db.commit()

    return {"message": "ok"}
