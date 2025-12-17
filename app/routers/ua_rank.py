"""
地下竞技场国服榜单 - 敲可爱战队500强
"""
import httpx
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db, get_current_user, require_admin_cookie
from app.models import User, UserProfile, UserRole, MemberSeasonRank

router = APIRouter(prefix="/api/ua-rank", tags=["ua-rank"])

# 暴雪API地址
BLIZZARD_MODE_API = "https://webapi.blizzard.cn/hs-rank-api-server/api/v2/game/mode"
BLIZZARD_RANKS_API = "https://webapi.blizzard.cn/hs-rank-api-server/api/game/ranks"


async def fetch_current_season_id() -> int:
    """获取当前赛季ID"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(BLIZZARD_MODE_API)
        resp.raise_for_status()
        data = resp.json()
        season_id = data['data']['season_map']['undergroundarena'][0]['season_id']
        return int(season_id)


async def fetch_ranks_page(season_id: int, page: int, page_size: int = 25) -> List[dict]:
    """获取指定赛季的排名数据（单页）"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            BLIZZARD_RANKS_API,
            params={
                "page": page,
                "page_size": page_size,
                "mode_name": "undergroundarena",
                "season_id": season_id,
            }
        )
        resp.raise_for_status()
        data = resp.json()
        # 处理 data 为 None 的情况
        inner_data = data.get("data") if data else None
        if inner_data is None:
            return []
        return inner_data.get("list", [])


async def fetch_all_ranks(season_id: int, max_pages: int = 20) -> List[dict]:
    """获取指定赛季的所有排名数据（1~max_pages页，最多500条）"""
    all_ranks = []
    for page in range(1, max_pages + 1):
        try:
            page_data = await fetch_ranks_page(season_id, page)
            if not page_data:
                break
            all_ranks.extend(page_data)
        except Exception as e:
            print(f"获取第{page}页排名失败: {e}")
            break
    return all_ranks


@router.get("/current-season")
async def get_current_season_leaderboard(db: Session = Depends(get_db)):
    """
    获取当前赛季地下竞技场国服榜单中的敲可爱战队成员
    """
    # 1. 获取赛季ID
    try:
        season_id = await fetch_current_season_id()
    except Exception as e:
        return {"error": True, "message": f"获取赛季ID失败: {str(e)}"}
    
    # 2. 获取排名数据（1~20页，共500条）
    try:
        all_ranks = await fetch_all_ranks(season_id, max_pages=20)
    except Exception as e:
        return {"error": True, "message": f"获取排名数据失败: {str(e)}"}
    
    if not all_ranks:
        return {"error": True, "message": "暂无排名数据"}
    
    # 3. 获取所有战队成员（member及以上角色）
    members = (
        db.query(User)
        .filter(User.role.in_([
            UserRole.MEMBER, UserRole.ELITE_MEMBER, 
            UserRole.ADMIN, UserRole.SUPER_ADMIN
        ]))
        .all()
    )
    
    # 构建 username/nickname -> user 的映射
    name_to_user = {}
    for m in members:
        name_to_user[m.username.lower()] = m
        if m.nickname:
            name_to_user[m.nickname.lower()] = m
    
    # 4. 匹配榜单中的战队成员
    matched_members = []
    matched_user_ids = set()
    
    for rank_data in all_ranks:
        battle_tag = rank_data.get("battle_tag", "")
        battle_tag_lower = battle_tag.lower()
        
        # 尝试匹配 username 或 nickname
        user = name_to_user.get(battle_tag_lower)
        if user and user.id not in matched_user_ids:
            matched_user_ids.add(user.id)
            
            # 获取用户 profile
            profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
            avatar_url = profile.avatar_url if profile else None
            
            matched_members.append({
                "user_id": user.id,
                "position": rank_data.get("position"),
                "battle_tag": battle_tag,
                "score": rank_data.get("score"),
                "nickname": user.nickname,
                "username": user.username,
                "avatar_url": avatar_url,
            })
            
            # 5. 更新 user_profiles
            if profile:
                # 更新当前赛季排名和分数
                profile.current_season_rank = rank_data.get("position")
                profile.current_season_score = rank_data.get("score")
                
                # 更新历史最佳排名（如果当前更好或为空）
                current_rank = rank_data.get("position")
                current_score = rank_data.get("score")
                
                # arena_best_rank 是字符串格式，如 "前100"
                if profile.arena_best_rank is None or profile.arena_best_rank == "":
                    profile.arena_best_rank = f"第{current_rank}名"
                else:
                    # 尝试解析现有排名
                    try:
                        old_rank_str = profile.arena_best_rank
                        if "第" in old_rank_str and "名" in old_rank_str:
                            old_rank = int(old_rank_str.replace("第", "").replace("名", ""))
                            if current_rank < old_rank:
                                profile.arena_best_rank = f"第{current_rank}名"
                    except:
                        pass
                
                # 更新历史最高分数
                if profile.best_season_score is None or current_score > profile.best_season_score:
                    profile.best_season_score = current_score
    
    db.commit()
    
    # 按排名排序
    matched_members.sort(key=lambda x: x["position"])
    
    return {
        "error": False,
        "season_id": season_id,
        "members": matched_members,
        "total": len(matched_members),
        "synced": True,
    }


@router.post("/sync-all-seasons")
async def sync_all_seasons(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_cookie),
):
    """
    同步所有历史赛季成绩到 member_season_ranks 表
    仅管理员可用
    """
    # 1. 获取当前赛季ID
    try:
        current_season_id = await fetch_current_season_id()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取赛季ID失败: {str(e)}")
    
    # 2. 获取所有战队成员
    members = (
        db.query(User)
        .filter(User.role.in_([
            UserRole.MEMBER, UserRole.ELITE_MEMBER, 
            UserRole.ADMIN, UserRole.SUPER_ADMIN
        ]))
        .all()
    )
    
    # 构建 username/nickname -> user 的映射
    name_to_user = {}
    for m in members:
        name_to_user[m.username.lower()] = m
        if m.nickname:
            name_to_user[m.nickname.lower()] = m
    
    # 3. 遍历所有赛季（从1到当前赛季）
    total_synced = 0
    synced_seasons = []
    
    for season_id in range(1, current_season_id + 1):
        try:
            # 每个赛季获取1~20页
            all_ranks = await fetch_all_ranks(season_id, max_pages=20)
            
            if not all_ranks:
                continue
            
            season_synced = 0
            
            for rank_data in all_ranks:
                battle_tag = rank_data.get("battle_tag", "")
                battle_tag_lower = battle_tag.lower()
                
                user = name_to_user.get(battle_tag_lower)
                if user:
                    # 检查是否已存在记录
                    existing = (
                        db.query(MemberSeasonRank)
                        .filter(
                            MemberSeasonRank.user_id == user.id,
                            MemberSeasonRank.season_id == season_id
                        )
                        .first()
                    )
                    
                    if existing:
                        # 更新
                        existing.rank = rank_data.get("position")
                        existing.score = rank_data.get("score")
                        existing.updated_at = datetime.utcnow()
                    else:
                        # 插入
                        new_record = MemberSeasonRank(
                            user_id=user.id,
                            season_id=season_id,
                            rank=rank_data.get("position"),
                            score=rank_data.get("score"),
                        )
                        db.add(new_record)
                    
                    season_synced += 1
            
            if season_synced > 0:
                synced_seasons.append({"season_id": season_id, "count": season_synced})
                total_synced += season_synced
                
        except Exception as e:
            print(f"同步赛季 {season_id} 失败: {e}")
            continue
    
    db.commit()
    
    return {
        "success": True,
        "total_synced": total_synced,
        "seasons": synced_seasons,
        "current_season_id": current_season_id,
    }


@router.get("/history/{user_id}")
async def get_user_season_history(
    user_id: int,
    db: Session = Depends(get_db),
):
    """获取用户的历史赛季成绩"""
    records = (
        db.query(MemberSeasonRank)
        .filter(MemberSeasonRank.user_id == user_id)
        .order_by(MemberSeasonRank.season_id.desc())
        .all()
    )
    
    return [
        {
            "season_id": r.season_id,
            "rank": r.rank,
            "score": r.score,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in records
    ]
