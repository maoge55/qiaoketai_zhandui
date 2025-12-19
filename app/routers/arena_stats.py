"""竞技场卡牌统计数据同步 API"""
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db, require_admin_cookie
from app.models import ArenaCardStats

router = APIRouter(prefix="/api/arena", tags=["arena-stats"])

# 职业映射：HSReplay 英文 -> 中文（与 cards 表一致）
CLASS_MAP = {
    "ALL": "全部职业",
    "DEATHKNIGHT": "死亡骑士",
    "DRUID": "德鲁伊",
    "HUNTER": "猎人",
    "MAGE": "法师",
    "PALADIN": "圣骑士",
    "PRIEST": "牧师",
    "ROGUE": "潜行者",
    "SHAMAN": "萨满",
    "WARLOCK": "术士",
    "WARRIOR": "战士",
    "DEMONHUNTER": "恶魔猎手",
}


@router.post("/sync-hdt-stats")
def sync_hdt_card_stats(
    current_user=Depends(require_admin_cookie),
    db: Session = Depends(get_db),
):
    """
    同步 HSReplay 竞技场卡牌统计数据（仅管理员可用）
    
    1. 获取 hearthstonejson 卡牌数据，建立 card['id'] -> card['dbfId'] 映射
    2. 获取 hsreplay 竞技场统计数据
    3. 更新或插入到 arena_card_stats 表
    """
    
    try:
        # 第一步：获取卡牌 ID 映射
        cards_url = "https://api.hearthstonejson.com/v1/latest/zhCN/cards.json"
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(cards_url)
            resp.raise_for_status()
            cards_data = resp.json()
        
        # 建立 card_id_str -> dbfId 的映射
        card_dict = {}
        for card in cards_data:
            card_id_str = card.get("id")  # 字符串 ID，如 "DREAM_05"
            dbf_id = card.get("dbfId")     # 数字 ID，对应我们的 card_id
            if card_id_str and dbf_id:
                card_dict[card_id_str] = dbf_id
        
        # 第二步：获取 HSReplay 竞技场统计数据
        stats_url = "https://hsreplay.net/api/v1/arena/card_stats/free/?ArenaTimestampRangeFilter=LAST_4_DAYS"
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(stats_url)
            resp.raise_for_status()
            stats_data = resp.json()
        
        data_section = stats_data.get("data", {})
        
        # 第三步：遍历所有职业数据，更新或插入到数据库
        updated_count = 0
        inserted_count = 0
        skipped_count = 0
        
        for class_key, class_cards in data_section.items():
            # 获取中文职业名
            card_class_cn = CLASS_MAP.get(class_key)
            if not card_class_cn:
                # 未知职业，跳过
                continue
            
            for card_stat in class_cards:
                # 获取卡牌的字符串 ID
                card_id_str = card_stat.get("card_id")
                if not card_id_str:
                    skipped_count += 1
                    continue
                
                # 转换为 dbfId
                dbf_id = card_dict.get(card_id_str)
                if not dbf_id:
                    # 找不到对应的 dbfId，跳过
                    skipped_count += 1
                    continue
                
                # 查找是否已存在
                existing = db.query(ArenaCardStats).filter(
                    ArenaCardStats.card_id == dbf_id,
                    ArenaCardStats.card_class == card_class_cn
                ).first()
                
                if existing:
                    # 更新
                    existing.popularity = card_stat.get("popularity")
                    existing.avg_copies_in_deck = card_stat.get("avg_copies_in_deck")
                    existing.win_rate = card_stat.get("win_rate")
                    existing.drawn_win_rate = card_stat.get("drawn_win_rate")
                    existing.played_win_rate = card_stat.get("played_win_rate")
                    existing.num_games = card_stat.get("num_games")
                    existing.updated_at = datetime.utcnow()
                    updated_count += 1
                else:
                    # 插入
                    new_stat = ArenaCardStats(
                        card_id=dbf_id,
                        popularity=card_stat.get("popularity"),
                        avg_copies_in_deck=card_stat.get("avg_copies_in_deck"),
                        win_rate=card_stat.get("win_rate"),
                        drawn_win_rate=card_stat.get("drawn_win_rate"),
                        played_win_rate=card_stat.get("played_win_rate"),
                        num_games=card_stat.get("num_games"),
                        card_class=card_class_cn,
                    )
                    db.add(new_stat)
                    inserted_count += 1
        
        db.commit()
        
        return {
            "success": True,
            "message": f"同步完成：新增 {inserted_count} 条，更新 {updated_count} 条，跳过 {skipped_count} 条",
            "inserted": inserted_count,
            "updated": updated_count,
            "skipped": skipped_count,
        }
    
    except httpx.HTTPError as e:
        raise HTTPException(500, f"请求外部 API 失败: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"同步失败: {str(e)}")
