from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies.auth import (
    get_db,
    require_member,
    get_current_user,
)
from app.models import User, UserProfile, UserRole, Achievement
from app.schemas import (
    UserProfileOut,
    UserProfileUpdate,
    AchievementOut,
)

router = APIRouter(prefix="/api", tags=["members"])


@router.get("/members", response_model=List[UserProfileOut])
def list_members(db: Session = Depends(get_db)):
    # 只展示角色 >= member 的用户
    members = (
        db.query(UserProfile)
        .join(User)
        .filter(
            User.role.in_(
                [UserRole.MEMBER, UserRole.ELITE_MEMBER, UserRole.ADMIN]
            )
        )
        .all()
    )

    result = []
    for p in members:
        result.append(
            UserProfileOut(
                user_id=p.user_id,
                avatar_url=p.avatar_url,
                age=p.age,
                gender=p.gender,
                strength_score=p.strength_score,
                bio=p.bio,
                avg_arena_wins=p.avg_arena_wins,
                arena_best_rank=p.arena_best_rank,
                other_tags=p.other_tags,
            )
        )
    return result


@router.get("/members/{user_id}")
def member_detail(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "成员不存在")
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname,
            "role": user.role.value,
        },
        "profile": UserProfileOut.from_orm(profile) if profile else None,
    }


@router.get(
    "/members/{user_id}/achievements", response_model=List[AchievementOut]
)
def member_achievements(user_id: int, db: Session = Depends(get_db)):
    achievements = (
        db.query(Achievement)
        .filter(Achievement.member_id == user_id)
        .order_by(Achievement.achieved_at.desc())
        .all()
    )
    result = []
    for a in achievements:
        result.append(
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
        )
    return result


@router.get("/me/profile", response_model=UserProfileOut)
def get_my_profile(current_user=Depends(require_member), db: Session = Depends(get_db)):
    profile = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == current_user.id)
        .first()
    )
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return UserProfileOut.from_orm(profile)


@router.put("/me/profile", response_model=UserProfileOut)
def update_my_profile(
    payload: UserProfileUpdate,
    current_user=Depends(require_member),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == current_user.id)
        .first()
    )
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)

    if payload.avatar_url is not None:
        profile.avatar_url = payload.avatar_url
    if payload.age is not None:
        profile.age = payload.age
    if payload.gender is not None:
        profile.gender = payload.gender
    if payload.strength_score is not None:
        profile.strength_score = payload.strength_score
    if payload.bio is not None:
        profile.bio = payload.bio
    if payload.avg_arena_wins is not None:
        profile.avg_arena_wins = payload.avg_arena_wins
    if payload.arena_best_rank is not None:
        profile.arena_best_rank = payload.arena_best_rank
    if payload.other_tags is not None:
        profile.other_tags = payload.other_tags

    if payload.nickname is not None:
        current_user.nickname = payload.nickname

    db.commit()
    db.refresh(profile)
    return UserProfileOut.from_orm(profile)
