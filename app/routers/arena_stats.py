"""竞技场卡牌统计数据同步 API"""
import asyncio
import threading
from datetime import datetime
from typing import Optional

import httpx
from curl_cffi import requests as curl_requests
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db, require_admin_cookie
from app.models import ArenaCardStats
from app.database import SessionLocal

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

# 同步状态
class SyncState:
    def __init__(self):
        self.is_syncing = False
        self.last_sync_time: Optional[datetime] = None
        self.last_sync_result: Optional[dict] = None
        self.sync_version = 0  # 用于前端检测是否有新数据
        self._lock = threading.Lock()
    
    def start_sync(self):
        with self._lock:
            if self.is_syncing:
                return False
            self.is_syncing = True
            return True
    
    def finish_sync(self, result: dict):
        with self._lock:
            self.is_syncing = False
            self.last_sync_time = datetime.utcnow()
            self.last_sync_result = result
            self.sync_version += 1
    
    def get_status(self):
        with self._lock:
            return {
                "is_syncing": self.is_syncing,
                "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
                "last_sync_result": self.last_sync_result,
                "sync_version": self.sync_version,
            }

sync_state = SyncState()


def do_sync_hdt_stats():
    """执行同步逻辑（可在后台线程运行）"""
    db = SessionLocal()
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
            card_id_str = card.get("id")
            dbf_id = card.get("dbfId")
            if card_id_str and dbf_id:
                card_dict[card_id_str] = dbf_id
        
        # 第二步：获取 HSReplay 竞技场统计数据（使用 curl_cffi 模拟 Chrome TLS 指纹）
        stats_url = "https://hsreplay.net/api/v1/arena/card_stats/free/?ArenaTimestampRangeFilter=LAST_4_DAYS"
        
        # 使用 curl_cffi 模拟 Chrome 浏览器
        resp = curl_requests.get(stats_url, impersonate="chrome", timeout=60)
        resp.raise_for_status()
        stats_data = resp.json()
        
        data_section = stats_data.get("data", {})
        
        # 第三步：遍历所有职业数据，更新或插入到数据库
        updated_count = 0
        inserted_count = 0
        skipped_count = 0
        
        for class_key, class_cards in data_section.items():
            card_class_cn = CLASS_MAP.get(class_key)
            if not card_class_cn:
                continue
            
            for card_stat in class_cards:
                card_id_str = card_stat.get("card_id")
                if not card_id_str:
                    skipped_count += 1
                    continue
                
                dbf_id = card_dict.get(card_id_str)
                if not dbf_id:
                    skipped_count += 1
                    continue
                
                existing = db.query(ArenaCardStats).filter(
                    ArenaCardStats.card_id == dbf_id,
                    ArenaCardStats.card_class == card_class_cn
                ).first()
                
                if existing:
                    existing.popularity = card_stat.get("popularity")
                    existing.avg_copies_in_deck = card_stat.get("avg_copies_in_deck")
                    existing.win_rate = card_stat.get("win_rate")
                    existing.drawn_win_rate = card_stat.get("drawn_win_rate")
                    existing.played_win_rate = card_stat.get("played_win_rate")
                    existing.num_games = card_stat.get("num_games")
                    existing.updated_at = datetime.utcnow()
                    updated_count += 1
                else:
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
    
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "message": f"同步失败: {str(e)}",
            "error": str(e),
        }
    finally:
        db.close()


def background_sync_task():
    """后台同步任务"""
    if not sync_state.start_sync():
        return  # 已在同步中
    
    try:
        result = do_sync_hdt_stats()
        sync_state.finish_sync(result)
    except Exception as e:
        sync_state.finish_sync({"success": False, "message": str(e)})


# 定时任务：每10分钟自动同步
_scheduler_started = False

async def auto_sync_scheduler():
    """自动同步调度器"""
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    
    # 等待应用启动完成
    await asyncio.sleep(5)
    
    while True:
        try:
            # 在线程池中执行同步
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, background_sync_task)
        except Exception as e:
            print(f"[HDT Sync] 自动同步失败: {e}")
        
        # 等待10分钟
        await asyncio.sleep(600)


def start_auto_sync():
    """启动自动同步（在应用启动时调用）"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(auto_sync_scheduler())
        else:
            loop.create_task(auto_sync_scheduler())
    except RuntimeError:
        # 没有事件循环，创建新的
        pass


@router.get("/sync-status")
def get_sync_status():
    """获取同步状态（无需登录）"""
    return sync_state.get_status()


@router.post("/sync-hdt-stats")
def sync_hdt_card_stats(
    background_tasks: BackgroundTasks,
    current_user=Depends(require_admin_cookie),
):
    """
    手动触发同步 HSReplay 竞技场卡牌统计数据（仅管理员可用）
    同步在后台执行，立即返回
    """
    if sync_state.is_syncing:
        return {
            "success": True,
            "message": "同步正在进行中，请稍后查看结果",
            "is_syncing": True,
        }
    
    # 在后台执行同步
    background_tasks.add_task(background_sync_task)
    
    return {
        "success": True,
        "message": "同步任务已启动，将在后台执行",
        "is_syncing": True,
    }


@router.post("/import-json")
def import_json_stats(
    current_user=Depends(require_admin_cookie),
):
    """
    从本地生成的 JSON 文件导入竞技场统计数据（仅管理员可用）
    JSON 文件应放在 app/static/uploads/arena_stats_data.json
    """
    import json
    import os
    
    json_path = os.path.join("app", "static", "uploads", "arena_stats_data.json")
    
    if not os.path.exists(json_path):
        raise HTTPException(
            status_code=404,
            detail=f"JSON 文件不存在，请先将 arena_stats_data.json 上传到 {json_path}"
        )
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取 JSON 失败: {str(e)}")
    
    data_list = json_data.get("data", [])
    if not data_list:
        raise HTTPException(status_code=400, detail="JSON 文件中没有数据")
    
    db = SessionLocal()
    try:
        updated_count = 0
        inserted_count = 0
        
        for item in data_list:
            card_id = item.get("card_id")
            card_class = item.get("card_class")
            if not card_id or not card_class:
                continue
            
            existing = db.query(ArenaCardStats).filter(
                ArenaCardStats.card_id == card_id,
                ArenaCardStats.card_class == card_class
            ).first()
            
            if existing:
                existing.popularity = item.get("popularity")
                existing.avg_copies_in_deck = item.get("avg_copies_in_deck")
                existing.win_rate = item.get("win_rate")
                existing.drawn_win_rate = item.get("drawn_win_rate")
                existing.played_win_rate = item.get("played_win_rate")
                existing.num_games = item.get("num_games")
                existing.updated_at = datetime.utcnow()
                updated_count += 1
            else:
                new_stat = ArenaCardStats(
                    card_id=card_id,
                    popularity=item.get("popularity"),
                    avg_copies_in_deck=item.get("avg_copies_in_deck"),
                    win_rate=item.get("win_rate"),
                    drawn_win_rate=item.get("drawn_win_rate"),
                    played_win_rate=item.get("played_win_rate"),
                    num_games=item.get("num_games"),
                    card_class=card_class,
                )
                db.add(new_stat)
                inserted_count += 1
        
        db.commit()
        
        # 更新同步状态
        sync_state.finish_sync({
            "success": True,
            "message": f"从 JSON 导入完成：新增 {inserted_count} 条，更新 {updated_count} 条",
            "inserted": inserted_count,
            "updated": updated_count,
            "source": "json_import",
        })
        
        return {
            "success": True,
            "message": f"导入完成：新增 {inserted_count} 条，更新 {updated_count} 条",
            "inserted": inserted_count,
            "updated": updated_count,
            "generated_at": json_data.get("generated_at"),
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")
    finally:
        db.close()
