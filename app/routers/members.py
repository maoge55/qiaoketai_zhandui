from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pathlib import Path
from sqlalchemy import case
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
import hashlib
router = APIRouter(prefix="/api", tags=["members"])

# 头像上传目录：app/static/avatars
BASE_DIR = Path(__file__).resolve().parent.parent  # app/
AVATAR_DIR = BASE_DIR / "static" / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

@router.get("/members", response_model=List[UserProfileOut])
def list_members(
    page: int = 1,
    page_size: int = 12,
    db: Session = Depends(get_db)):
    # 分页安全处理
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 50:
        page_size = 12

    # 只展示战队成员及以上
    q = (
        db.query(UserProfile)
        .join(User)
        .filter(
            User.role.in_(
                [UserRole.MEMBER, UserRole.ELITE_MEMBER, UserRole.ADMIN]
            )
        )
    )

    # NULL 排到后面
    rank_is_null = case(
        (UserProfile.current_season_rank.is_(None), 1),
        else_=0,
    )

    # ✅ 排序规则：
    # 1）影响力高的排在前面（desc）
    # 2）有当前赛季排名的排在前面，名次数字越小越靠前
    # 3）然后按用户 id 稳定排序
    q = q.order_by(
        UserProfile.influence.desc(),
        rank_is_null,
        UserProfile.current_season_rank.asc(),
        User.id.asc(),
    )

    profiles = (
        q.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return profiles


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

@router.post("/me/avatar")
async def upload_my_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    当前登录用户上传头像：
    - 所有已登录用户都可以调用（不限制角色）
    - 同一邮箱用户只保留一张头像文件
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="未登录，无法上传头像")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只能上传图片类型文件")

    # 限制类型：JPG / PNG / WEBP
    allowed_types = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    ext = allowed_types.get(file.content_type)
    if not ext:
        raise HTTPException(
            status_code=400,
            detail="只支持 JPG / PNG / WEBP 格式的头像",
        )

    # 按邮箱生成唯一文件名（邮箱本身在 users 表中是唯一的）
    email = (current_user.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="当前账号没有绑定邮箱，无法上传头像")

    email_hash = hashlib.md5(email.encode("utf-8")).hexdigest()

    # 清理旧文件：同一 hash 前缀的文件全部删掉，保证后端只保留一份
    for old in AVATAR_DIR.glob(f"{email_hash}.*"):
        try:
            old.unlink()
        except OSError:
            # 不影响主流程
            pass

    filename = f"{email_hash}{ext}"
    file_path = AVATAR_DIR / filename

    # 读入文件并限制大小（示例：最大 2MB）
    data = await file.read()
    max_size = 2 * 1024 * 1024  # 2MB
    if len(data) > max_size:
        raise HTTPException(status_code=400, detail="头像文件不能超过 2MB")

    file_path.write_bytes(data)

    # 更新 / 创建 UserProfile 头像字段
    profile = (
        db.query(UserProfile)
        .filter(UserProfile.user_id == current_user.id)
        .first()
    )
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)

    # 存的是可直接访问的 URL
    profile.avatar_url = f"/static/avatars/{filename}"

    db.commit()
    db.refresh(profile)

    return {"avatar_url": profile.avatar_url}
