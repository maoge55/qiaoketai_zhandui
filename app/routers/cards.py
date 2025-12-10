from typing import List, Optional
import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db
from app.models import Card
from app.schemas import CardOut

router = APIRouter(prefix="/api/cards", tags=["cards"])

@router.get("", response_model=List[CardOut])
def list_cards(
    db: Session = Depends(get_db),
    # 版本筛选（你下拉框用的）
    version: Optional[str] = Query(None, description="按 cards.version 过滤"),
    # 兼容老的 expansion 参数（不想用可以以后删）
    expansion: Optional[str] = Query(
        None, description="兼容老参数，按 expansion 过滤（可选）"
    ),
    # ✅ 新增：职业筛选
    card_class: Optional[str] = Query(
        None, description="按职业过滤"
    ),
    # ✅ 新增：稀有度筛选
    rarity: Optional[str] = Query(
        None, description="按稀有度过滤"
    ),
    # 模糊搜索
    search: Optional[str] = Query(
        None, description="模糊搜索卡牌名"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
):
    query = db.query(Card)

    if version:
        query = query.filter(Card.version == version)
    elif expansion:
        query = query.filter(Card.expansion == expansion)

    if card_class:
        query = query.filter(Card.card_class == card_class)

    if rarity:
        query = query.filter(Card.rarity == rarity)

    if search:
        like = f"%{search}%"
        query = query.filter(Card.name.ilike(like))

    # 注意：SQL Server 不支持 NULLS LAST，这里不要加 .nullslast()
    query = query.order_by(Card.mana_cost.asc(), Card.name.asc())

    cards = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return cards

@router.get("/expansions", response_model=List[str])
def list_versions(db: Session = Depends(get_db)):
    """
    下拉框用的版本列表：
    - 实际返回的是 cards.version
    - 排序规则：按 expansion 中 () 里的年份倒序（新的在前）
      比如 '天马年 (2024)' 会排在 '独狼年 (2023)' 前面
    """
    # 拿到 version + expansion 的去重组合
    rows = db.query(distinct(Card.version), Card.expansion).all()

    items = []
    for version, expansion in rows:
        # 没 version 就没必要出现在下拉框里
        if not version:
            continue

        year = 0
        if expansion:
            # 匹配括号里的 4 位数字年份：(... 2024)
            m = re.search(r"\((\d{4})\)", expansion)
            if m:
                year = int(m.group(1))

        items.append(
            {
                "version": version,
                "expansion": expansion or "",
                "year": year,
            }
        )

    # 按年份倒序，其次按 version 倒序
    items.sort(key=lambda x: (x["year"], x["version"]), reverse=True)

    # 前端只需要 version 文本
    return [item["version"] for item in items]

@router.get("/classes", response_model=List[str])
def list_classes(db: Session = Depends(get_db)):
    """卡牌职业列表"""
    rows = (
        db.query(distinct(Card.card_class))
        .filter(Card.card_class.isnot(None))
        .all()
    )
    return [r[0] for r in rows if r[0]]


@router.get("/rarities", response_model=List[str])
def list_rarities(db: Session = Depends(get_db)):
    """卡牌稀有度列表"""
    rows = (
        db.query(distinct(Card.rarity))
        .filter(Card.rarity.isnot(None))
        .all()
    )
    return [r[0] for r in rows if r[0]]