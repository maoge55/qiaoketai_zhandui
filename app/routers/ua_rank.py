"""
地下竞技场国服榜单 - 敲可爱战队500强
"""
import httpx
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db, get_current_user, require_admin_cookie
from app.models import User, UserProfile, UserRole, MemberSeasonRank

router = APIRouter(prefix="/api/ua-rank", tags=["ua-rank"])

# 暴雪API地址
BLIZZARD_MODE_API = "https://webapi.blizzard.cn/hs-rank-api-server/api/v2/game/mode"
BLIZZARD_RANKS_API = "https://webapi.blizzard.cn/hs-rank-api-server/api/game/ranks"

# 缓存配置：10分钟更新一次
CACHE_TTL_SECONDS = 600  # 10分钟

# 全局缓存
_leaderboard_cache: Dict[str, Any] = {
    "data": None,
    "last_updated": None,
    "season_id": None,
}

# 影响力档位定义：档位越高奖励越多
# 档位: (最大排名, 该档位奖励值)
INFLUENCE_TIERS = [
    (1, 100),    # 第1名: +100
    (3, 60),     # 前3名: +60
    (10, 30),    # 前10名: +30
    (50, 20),    # 前50名: +20
    (200, 10),   # 前200名: +10
    (500, 5),    # 前500名: +5
]


def get_rank_tier(rank: int) -> int:
    """
    根据排名获取档位 (6=第1, 5=前3, 4=前10, 3=前50, 2=前200, 1=前500, 0=500名开外)
    档位数字越大表示排名越靠前
    """
    if rank == 1:
        return 6
    elif rank <= 3:
        return 5
    elif rank <= 10:
        return 4
    elif rank <= 50:
        return 3
    elif rank <= 200:
        return 2
    elif rank <= 500:
        return 1
    else:
        return 0


def calculate_influence_gain(old_tier: int, new_tier: int) -> int:
    """
    计算从旧档位升到新档位应获得的影响力增量
    档位对应奖励: 1=+5, 2=+10, 3=+20, 4=+30, 5=+60, 6=+100
    """
    tier_rewards = {1: 5, 2: 10, 3: 20, 4: 30, 5: 60, 6: 100}
    
    if new_tier <= old_tier:
        return 0  # 没有提升或下降，不获得奖励
    
    # 累加从 old_tier+1 到 new_tier 的所有奖励
    gain = 0
    for tier in range(old_tier + 1, new_tier + 1):
        gain += tier_rewards.get(tier, 0)
    
    return gain


async def fetch_current_season_id(max_retries: int = 5) -> int:
    """获取当前赛季ID，支持重试"""
    import asyncio
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=80.0) as client:
                resp = await client.get(BLIZZARD_MODE_API)
                resp.raise_for_status()
                data = resp.json()
                season_id = data['data']['season_map']['undergroundarena'][0]['season_id']
                return int(season_id)
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"获取赛季ID失败(尝试{attempt+1}/{max_retries}): {e}")
                await asyncio.sleep(2 * (attempt + 1))
                continue
            else:
                raise e
    raise Exception("获取赛季ID失败")


async def fetch_ranks_page(season_id: int, page: int, page_size: int = 25, max_retries: int = 5) -> List[dict]:
    """获取指定赛季的排名数据（单页），支持重试"""
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=80.0) as client:
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
        except Exception as e:
            if attempt < max_retries - 1:
                # 等待后重试，指数退避
                import asyncio
                await asyncio.sleep(1 * (attempt + 1))
                continue
            else:
                raise e
    return []


async def fetch_all_ranks(season_id: int, max_pages: int = 20, max_retries: int = 3) -> List[dict]:
    """获取指定赛季的所有排名数据（1~max_pages页，最多500条），支持重试"""
    import asyncio
    all_ranks = []
    for page in range(1, max_pages + 1):
        for attempt in range(max_retries):
            try:
                page_data = await fetch_ranks_page(season_id, page, max_retries=max_retries)
                if not page_data:
                    # 空数据，说明没有更多页了
                    return all_ranks
                all_ranks.extend(page_data)
                break  # 成功，跳出重试循环
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"获取赛季{season_id}第{page}页失败(尝试{attempt+1}/{max_retries}): {e}")
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                else:
                    print(f"获取赛季{season_id}第{page}页最终失败: {e}")
                    # 最后一次重试仍失败，返回已获取的数据
                    return all_ranks
    return all_ranks


@router.get("/current-season")
async def get_current_season_leaderboard(db: Session = Depends(get_db)):
    """
    获取当前赛季地下竞技场国服榜单中的敲可爱战队成员
    使用缓存，每10分钟更新一次
    """
    global _leaderboard_cache
    
    now = datetime.utcnow()
    
    # 检查缓存是否有效
    cache_valid = False
    if _leaderboard_cache["last_updated"] and _leaderboard_cache["data"]:
        age = (now - _leaderboard_cache["last_updated"]).total_seconds()
        if age < CACHE_TTL_SECONDS:
            cache_valid = True
    
    if cache_valid:
        # 使用缓存数据
        cached = _leaderboard_cache["data"]
        last_updated = _leaderboard_cache["last_updated"]
        next_update = last_updated + timedelta(seconds=CACHE_TTL_SECONDS)
        seconds_until_update = max(0, int((next_update - now).total_seconds()))
        
        return {
            **cached,
            "cached": True,
            "last_updated": last_updated.isoformat(),
            "next_update": next_update.isoformat(),
            "seconds_until_update": seconds_until_update,
        }
    
    # 缓存过期或不存在，重新拉取数据
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
                current_rank = rank_data.get("position")
                current_score = rank_data.get("score")
                profile.current_season_rank = current_rank
                profile.current_season_score = current_score
                
                # ========== 影响力计算 ==========
                # 只有分数 >= 5000 才开始计算影响力
                if current_score and current_score >= 5000:
                    new_tier = get_rank_tier(current_rank)
                    
                    # 检查是否是新赛季（需要重置已获得档位）
                    if profile.influence_claimed_season_id != season_id:
                        profile.influence_claimed_season_id = season_id
                        profile.influence_tier_claimed = 0
                    
                    old_tier = profile.influence_tier_claimed or 0
                    
                    # 如果当前档位比已获得档位更高，发放奖励
                    if new_tier > old_tier:
                        influence_gain = calculate_influence_gain(old_tier, new_tier)
                        if influence_gain > 0:
                            profile.influence = (profile.influence or 1) + influence_gain
                            profile.influence_tier_claimed = new_tier
                
                # ========== 历史最佳排名更新 ==========
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
    
    # 构建返回数据
    result_data = {
        "error": False,
        "season_id": season_id,
        "members": matched_members,
        "total": len(matched_members),
        "synced": True,
    }
    
    # 更新缓存
    _leaderboard_cache["data"] = result_data
    _leaderboard_cache["last_updated"] = now
    _leaderboard_cache["season_id"] = season_id
    
    next_update = now + timedelta(seconds=CACHE_TTL_SECONDS)
    
    return {
        **result_data,
        "cached": False,
        "last_updated": now.isoformat(),
        "next_update": next_update.isoformat(),
        "seconds_until_update": CACHE_TTL_SECONDS,
    }


@router.post("/sync-all-seasons")
async def sync_all_seasons(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_cookie),
):
    """
    同步所有历史赛季成绩到 member_season_ranks 表（不含当前赛季）
    仅管理员可用，跳过已同步的赛季
    """
    import time
    start_time = time.time()
    
    # 1. 获取当前赛季ID（带重试）
    current_season_id = None
    for attempt in range(5):
        try:
            current_season_id = await fetch_current_season_id()
            break
        except Exception as e:
            if attempt < 4:
                import asyncio
                await asyncio.sleep(2 * (attempt + 1))
                continue
            else:
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
    
    if not members:
        return {"success": True, "message": "无战队成员", "total_synced": 0}
    
    # 构建 username/nickname -> user 的映射
    name_to_user = {}
    member_ids = set()
    for m in members:
        name_to_user[m.username.lower()] = m
        member_ids.add(m.id)
        if m.nickname:
            name_to_user[m.nickname.lower()] = m
    
    # 3. 查询已同步的赛季（数据库中已有记录的赛季）
    synced_season_ids = set(
        row[0] for row in db.query(MemberSeasonRank.season_id)
        .filter(MemberSeasonRank.user_id.in_(member_ids))
        .distinct()
        .all()
    )
    
    # 4. 遍历历史赛季（从1到当前赛季-1，跳过已同步的）
    total_synced = 0
    synced_seasons = []
    skipped_seasons = []
    failed_seasons = []
    
    # 只同步历史赛季（不含当前赛季）
    max_season = current_season_id - 1
    
    for season_id in range(1, max_season + 1):
        # 如果该赛季已有数据，跳过
        if season_id in synced_season_ids:
            skipped_seasons.append(season_id)
            continue
        
        # 每个赛季最多重试3次
        season_success = False
        for season_attempt in range(3):
            try:
                # 每个赛季获取1~20页
                all_ranks = await fetch_all_ranks(season_id, max_pages=20, max_retries=3)
                
                if not all_ranks:
                    season_success = True  # 空数据也算成功
                    break
                
                season_synced = 0
                
                for rank_data in all_ranks:
                    battle_tag = rank_data.get("battle_tag", "")
                    battle_tag_lower = battle_tag.lower()
                    
                    user = name_to_user.get(battle_tag_lower)
                    if user:
                        # 插入新记录（已跳过已存在的赛季，所以这里直接插入）
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
                    # 每同步一个赛季就提交，避免长事务
                    db.commit()
                
                season_success = True
                break
                    
            except Exception as e:
                print(f"同步赛季 {season_id} 失败(尝试{season_attempt+1}/3): {e}")
                if season_attempt < 2:
                    import asyncio
                    await asyncio.sleep(2 * (season_attempt + 1))
                    continue
        
        if not season_success:
            failed_seasons.append(season_id)
    
    end_time = time.time()
    duration_seconds = round(end_time - start_time, 2)
    
    # 格式化耗时
    if duration_seconds >= 60:
        minutes = int(duration_seconds // 60)
        seconds = int(duration_seconds % 60)
        duration_str = f"{minutes}分{seconds}秒"
    else:
        duration_str = f"{duration_seconds}秒"
    
    return {
        "success": True,
        "total_synced": total_synced,
        "seasons": synced_seasons,
        "skipped_seasons": len(skipped_seasons),
        "failed_seasons": failed_seasons,
        "current_season_id": current_season_id,
        "duration_seconds": duration_seconds,
        "duration_str": duration_str,
    }


@router.post("/sync-season-client")
async def sync_season_from_client(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_cookie),
):
    """
    接收客户端提交的赛季数据并入库
    客户端直接请求暴雪API后把数据POST过来
    """
    season_id = data.get("season_id")
    ranks = data.get("ranks", [])
    
    if not season_id or not isinstance(ranks, list):
        raise HTTPException(status_code=400, detail="参数错误")
    
    # 获取所有战队成员
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
    
    synced_count = 0
    
    for rank_data in ranks:
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
                existing.rank = rank_data.get("position")
                existing.score = rank_data.get("score")
                existing.updated_at = datetime.utcnow()
            else:
                new_record = MemberSeasonRank(
                    user_id=user.id,
                    season_id=season_id,
                    rank=rank_data.get("position"),
                    score=rank_data.get("score"),
                )
                db.add(new_record)
            
            synced_count += 1
    
    db.commit()
    
    return {
        "success": True,
        "season_id": season_id,
        "synced_count": synced_count,
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
