# app/routers/card_reviews.py
from typing import Optional

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db, require_member
from app.models import Card, CardReview, User, UserRole
from app.schemas import (
    CardReviewCardInfo,
    CardReviewItem,
    CardReviewReviewer,
    CardReviewsResponse,
    CardReviewUpsert,
    CardReviewMineOut,
    Pagination,
)

router = APIRouter(
    prefix="/api/v1/cards",
    tags=["card-reviews"],
)


@router.get("/{card_id}/reviews/me", response_model=Optional[CardReviewMineOut])
def get_my_review(
    card_id: int,
    current_user: User = Depends(require_member),
    db: Session = Depends(get_db),
):
    """获取我对某张卡的点评（用于二次编辑自动回填）。"""

    r = (
        db.query(CardReview)
        .filter(
            CardReview.card_id == card_id,
            CardReview.reviewer_id == current_user.id,
        )
        .first()
    )
    if not r:
        return None
    return CardReviewMineOut(
        review_id=r.id,
        score=r.score,
        content=r.content,
        created_at=r.created_at,
        game_version=r.game_version,
    )


@router.post("/{card_id}/reviews", response_model=CardReviewMineOut)
def upsert_review(
    card_id: int,
    payload: CardReviewUpsert,
    current_user: User = Depends(require_member),
    db: Session = Depends(get_db),
):
    """写/更新卡牌短评（同一人重复提交会覆盖更新）。

    约束：每张卡最多 5 个不同用户写短评。
    """

    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="卡牌不存在")

    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="短评内容不能为空")
    if len(content) > 200:
        raise HTTPException(status_code=400, detail="短评最多 200 字")

    # 分数简单限制：0-10
    if payload.score < 0 or payload.score > 10:
        raise HTTPException(status_code=400, detail="评分范围为 0~10")

    existing = (
        db.query(CardReview)
        .filter(
            CardReview.card_id == card_id,
            CardReview.reviewer_id == current_user.id,
        )
        .first()
    )

    if existing:
        existing.score = payload.score
        existing.content = content
        existing.game_version = payload.game_version
        # 这里用 created_at 作为“最后更新时间”，避免额外加字段
        existing.created_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return CardReviewMineOut(
            review_id=existing.id,
            score=existing.score,
            content=existing.content,
            created_at=existing.created_at,
            game_version=existing.game_version,
        )

    # 新增：限制每卡最多 5 人
    cnt = db.query(func.count(CardReview.id)).filter(CardReview.card_id == card_id).scalar() or 0
    if cnt >= 5:
        raise HTTPException(status_code=400, detail="该卡牌点评名额已满（最多 5 人）")

    review = CardReview(
        card_id=card_id,
        reviewer_id=current_user.id,
        score=payload.score,
        content=content,
        game_version=payload.game_version,
        created_at=datetime.utcnow(),
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    return CardReviewMineOut(
        review_id=review.id,
        score=review.score,
        content=review.content,
        created_at=review.created_at,
        game_version=review.game_version,
    )


@router.get("/{card_id}/reviews", response_model=CardReviewsResponse)
def get_card_reviews(
    card_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    sort: str = Query(
        "time_desc",
        description="排序方式：time_desc / time_asc / score_desc / score_asc",
    ),
    min_score: Optional[float] = Query(None, ge=0.0, description="只看高分评价：最小分数"),
    latest_version_only: bool = Query(
        False, description="是否只看该卡牌最新版本的评价"
    ),
    db: Session = Depends(get_db),
):
    # 1. 先拿到卡牌信息
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="卡牌不存在")

    # 2. 构造基础查询
    query = db.query(CardReview).filter(CardReview.card_id == card_id)

    if min_score is not None:
        query = query.filter(CardReview.score >= min_score)

    if latest_version_only:
        latest_version_subq = (
            db.query(func.max(CardReview.game_version))
            .filter(CardReview.card_id == card_id)
            .scalar_subquery()
        )
        query = query.filter(CardReview.game_version == latest_version_subq)

    total = query.count()

    # 3. 排序逻辑
    if sort.startswith("time"):
        order_col = CardReview.created_at
    else:
        order_col = CardReview.score

    if sort.endswith("desc"):
        order_by = desc(order_col)
    else:
        order_by = asc(order_col)

    reviews = (
        query.order_by(order_by)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 4. 计算平均分
    avg_score = (
        db.query(func.avg(CardReview.score))
        .filter(CardReview.card_id == card_id)
        .scalar()
    )
    average_score = round(avg_score, 1) if avg_score is not None else None

    # 5. 拼装返回结构
    card_info = CardReviewCardInfo(
        id=card.id,
        name=card.name,
        image_url=card.pic,
        average_score=average_score,
        card_class=card.card_class,
    )

    review_items: list[CardReviewItem] = []
    for r in reviews:
        u = r.reviewer
        # 简单规则：elite_member / admin 视为“专家”
        is_expert = u.role in (UserRole.ELITE_MEMBER, UserRole.ADMIN)

        review_items.append(
            CardReviewItem(
                review_id=r.id,
                reviewer=CardReviewReviewer(
                    id=u.id,
                    name=u.nickname or u.username,
                    is_expert=is_expert,
                ),
                score=r.score,
                content=r.content,
                created_at=r.created_at,
                game_version=r.game_version,
            )
        )

    return CardReviewsResponse(
        card_info=card_info,
        reviews=review_items,
        pagination=Pagination(page=page, total=total),
    )
