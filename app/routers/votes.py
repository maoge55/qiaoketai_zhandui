from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db, get_current_user_from_cookie_required
from app.models import Article, CardReview, CardReviewVote, GuideVote
from app.schemas import VoteRequest, VoteResponse

router = APIRouter(prefix="/api", tags=["votes"])


def _action_to_int(action: str) -> int:
    if action == "up":
        return 1
    if action == "down":
        return -1
    raise HTTPException(status_code=400, detail="action 仅支持 up/down")


def _int_to_action(v: int | None) -> str | None:
    if v == 1:
        return "up"
    if v == -1:
        return "down"
    return None


@router.post("/reviews/{review_id}/vote", response_model=VoteResponse)
def vote_review(
    review_id: int,
    payload: VoteRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_cookie_required),
):
    review = db.query(CardReview).filter(CardReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="点评不存在")

    target = _action_to_int(payload.action)

    existing = (
        db.query(CardReviewVote)
        .filter(
            CardReviewVote.review_id == review_id,
            CardReviewVote.user_id == current_user.id,
        )
        .first()
    )

    # 无记录：尝试插入（并发下可能触发唯一约束）
    if not existing:
        vote = CardReviewVote(
            review_id=review_id,
            user_id=current_user.id,
            action_type=target,
            created_at=datetime.utcnow(),
        )
        db.add(vote)
        try:
            if target == 1:
                review.upvote_count = int(review.upvote_count or 0) + 1
            else:
                review.downvote_count = int(review.downvote_count or 0) + 1
            db.commit()
        except IntegrityError:
            db.rollback()
            # 重新读取后走“已有记录”的逻辑
            existing = (
                db.query(CardReviewVote)
                .filter(
                    CardReviewVote.review_id == review_id,
                    CardReviewVote.user_id == current_user.id,
                )
                .first()
            )

    # 已有记录：同态取消 / 异态切换
    if existing:
        if existing.action_type == target:
            # cancel
            if target == 1:
                review.upvote_count = max(0, int(review.upvote_count or 0) - 1)
            else:
                review.downvote_count = max(0, int(review.downvote_count or 0) - 1)
            db.delete(existing)
            db.commit()
            return VoteResponse(
                action="cancelled",
                current_action=None,
                upvote_count=int(review.upvote_count or 0),
                downvote_count=int(review.downvote_count or 0),
            )

        # switch
        if existing.action_type == 1:
            review.upvote_count = max(0, int(review.upvote_count or 0) - 1)
        else:
            review.downvote_count = max(0, int(review.downvote_count or 0) - 1)

        existing.action_type = target
        existing.created_at = datetime.utcnow()

        if target == 1:
            review.upvote_count = int(review.upvote_count or 0) + 1
        else:
            review.downvote_count = int(review.downvote_count or 0) + 1

        db.commit()
        return VoteResponse(
            action="switched",
            current_action=_int_to_action(target),
            upvote_count=int(review.upvote_count or 0),
            downvote_count=int(review.downvote_count or 0),
        )

    # 新增成功
    return VoteResponse(
        action="added",
        current_action=_int_to_action(target),
        upvote_count=int(review.upvote_count or 0),
        downvote_count=int(review.downvote_count or 0),
    )


@router.post("/guides/{guide_id}/vote", response_model=VoteResponse)
def vote_guide(
    guide_id: int,
    payload: VoteRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_from_cookie_required),
):
    article = db.query(Article).filter(Article.id == guide_id).first()
    if not article or getattr(article, "status", None) is None:
        raise HTTPException(status_code=404, detail="文章不存在")

    target = _action_to_int(payload.action)

    existing = (
        db.query(GuideVote)
        .filter(
            GuideVote.article_id == guide_id,
            GuideVote.user_id == current_user.id,
        )
        .first()
    )

    influence_changed = 0

    def apply_influence(delta_like: int) -> None:
        nonlocal influence_changed
        if delta_like == 0:
            return
        author = getattr(article, "author", None)
        profile = getattr(author, "profile", None) if author else None
        if not profile:
            return
        profile.influence = int(profile.influence or 0) + delta_like
        influence_changed = delta_like

    # 无记录：插入
    if not existing:
        vote = GuideVote(
            article_id=guide_id,
            user_id=current_user.id,
            action_type=target,
            created_at=datetime.utcnow(),
        )
        db.add(vote)
        try:
            if target == 1:
                article.upvote_count = int(article.upvote_count or 0) + 1
                apply_influence(+1)
            else:
                article.downvote_count = int(article.downvote_count or 0) + 1
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = (
                db.query(GuideVote)
                .filter(
                    GuideVote.article_id == guide_id,
                    GuideVote.user_id == current_user.id,
                )
                .first()
            )

    if existing:
        if existing.action_type == target:
            # cancel
            if target == 1:
                article.upvote_count = max(0, int(article.upvote_count or 0) - 1)
                apply_influence(-1)
            else:
                article.downvote_count = max(0, int(article.downvote_count or 0) - 1)
            db.delete(existing)
            db.commit()
            return VoteResponse(
                action="cancelled",
                current_action=None,
                upvote_count=int(article.upvote_count or 0),
                downvote_count=int(article.downvote_count or 0),
                influence_changed=influence_changed,
            )

        # switch
        # 旧是赞 -> 新是踩：失去赞，影响力 -1
        if existing.action_type == 1:
            article.upvote_count = max(0, int(article.upvote_count or 0) - 1)
            apply_influence(-1)
        else:
            article.downvote_count = max(0, int(article.downvote_count or 0) - 1)

        existing.action_type = target
        existing.created_at = datetime.utcnow()

        # 新是赞 -> 影响力 +1
        if target == 1:
            article.upvote_count = int(article.upvote_count or 0) + 1
            apply_influence(+1)
        else:
            article.downvote_count = int(article.downvote_count or 0) + 1

        db.commit()
        return VoteResponse(
            action="switched",
            current_action=_int_to_action(target),
            upvote_count=int(article.upvote_count or 0),
            downvote_count=int(article.downvote_count or 0),
            influence_changed=influence_changed,
        )

    return VoteResponse(
        action="added",
        current_action=_int_to_action(target),
        upvote_count=int(article.upvote_count or 0),
        downvote_count=int(article.downvote_count or 0),
        influence_changed=influence_changed,
    )
