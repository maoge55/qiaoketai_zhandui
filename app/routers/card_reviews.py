# app/routers/card_reviews.py
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db
from app.models import Card, CardReview, UserRole
from app.schemas import (
    CardReviewCardInfo,
    CardReviewItem,
    CardReviewReviewer,
    CardReviewsResponse,
    Pagination,
)

router = APIRouter(
    prefix="/api/v1/cards",
    tags=["card-reviews"],
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
        is_expert = u.role in (UserRole.elite_member, UserRole.admin)

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
