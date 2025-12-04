from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db
from app.models import Achievement
from app.schemas import AchievementOut

router = APIRouter(prefix="/api", tags=["achievements"])


@router.get("/achievements", response_model=List[AchievementOut])
def list_achievements(
    member_id: Optional[int] = None,
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Achievement)
    if member_id:
        query = query.filter(Achievement.member_id == member_id)
    if from_date:
        query = query.filter(Achievement.achieved_at >= from_date)
    if to_date:
        query = query.filter(Achievement.achieved_at <= to_date)
    query = query.order_by(Achievement.achieved_at.desc())

    achievements = query.all()
    return [
        AchievementOut(
            id=a.id,
            member_id=a.member_id,
            member_nickname=a.member.nickname,
            title=a.title,
            description=a.description,
            season_or_version=a.season_or_version,
            rank_or_result=a.rank_or_result,
            achieved_at=a.achieved_at,
        )
        for a in achievements
    ]


@router.get("/achievements/featured", response_model=List[AchievementOut])
def featured_achievements(db: Session = Depends(get_db)):
    # 简单做法：取最新的 6 条
    achievements = (
        db.query(Achievement)
        .order_by(Achievement.achieved_at.desc())
        .limit(6)
        .all()
    )
    return [
        AchievementOut(
            id=a.id,
            member_id=a.member_id,
            member_nickname=a.member.nickname,
            title=a.title,
            description=a.description,
            season_or_version=a.season_or_version,
            rank_or_result=a.rank_or_result,
            achieved_at=a.achieved_at,
        )
        for a in achievements
    ]
