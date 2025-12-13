from typing import List, Optional
import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func, case
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db
from app.models import Card, CardReview, User, UserProfile
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
    sort_by: Optional[str] = Query(
        "mana", description="排序字段：class|win|mana|score"
    ),
    sort_order: str = Query(
        "asc", regex="^(asc|desc)$", description="排序方向"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
):
    # 均分子查询：给“按评分”排序用
    avg_sub = (
        db.query(
            CardReview.card_id.label("cid"),
            func.avg(CardReview.score).label("avg_score"),
        )
        .group_by(CardReview.card_id)
        .subquery()
    )

    query = (
        db.query(Card, avg_sub.c.avg_score.label("avg_score"))
        .outerjoin(avg_sub, Card.id == avg_sub.c.cid)
    )

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

    # 注意：SQL Server 不支持 NULLS LAST，这里用 case 把 NULL 排在后面
    def direction(expr):
        return expr.asc() if sort_order.lower() == "asc" else expr.desc()

    def nulls_last(expr):
        return case((expr.is_(None), 1), else_=0)

    if sort_by == "class":
        query = query.order_by(direction(Card.card_class), Card.mana_cost.asc(), Card.name.asc())
    elif sort_by == "win":
        query = query.order_by(nulls_last(Card.arena_score), direction(Card.arena_score), Card.name.asc())
    elif sort_by == "score":
        query = query.order_by(nulls_last(avg_sub.c.avg_score), direction(avg_sub.c.avg_score), Card.name.asc())
    else:  # 默认按水晶排序
        query = query.order_by(direction(Card.mana_cost), Card.name.asc())

    rows = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    cards = []
    avg_map: dict[int, float | None] = {}
    for row in rows:
        card, avg_score = row
        cards.append(card)
        if avg_score is not None:
            avg_map[card.id] = float(avg_score)

    # 补充点评均分（避免 SQL Server DISTINCT/文本问题，这里单独查均分）
    card_ids = [c.id for c in cards]
    top_map = {}

    if card_ids:
        # 取影响力最高的点评（若影响力为空，则排在后面），用于列表页展示点评人和短评
        influence_null_last = case((UserProfile.influence.is_(None), 1), else_=0)
        top_reviews = (
            db.query(
                CardReview.card_id,
                CardReview.content,
                User.nickname.label("nick"),
                User.username.label("uname"),
                UserProfile.influence,
                CardReview.created_at,
            )
            .join(User, User.id == CardReview.reviewer_id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .filter(CardReview.card_id.in_(card_ids))
            .order_by(influence_null_last, UserProfile.influence.desc(), CardReview.created_at.desc())
            .all()
        )

        seen = set()
        for cid, content, nick, uname, _, _ in top_reviews:
            if cid in seen:
                continue
            seen.add(cid)
            top_map[cid] = {
                "content": content,
                "reviewer": nick or uname or "",
            }

    # 构造响应模型，避免给 ORM property 赋值
    result: list[CardOut] = []
    for c in cards:
        top = top_map.get(c.id)
        result.append(
            CardOut(
                id=c.id,
                name=c.name,
                expansion=c.expansion,
                mana_cost=c.mana_cost,
                card_class=c.card_class,
                rarity=c.rarity,
                version=c.version,
                pic=c.pic,
                description=c.description,
                arena_score=c.arena_score,
                arena_win_rates=c.arena_win_rates,
                short_review=top["content"] if top else c.short_review,
                reviewer_nickname=top["reviewer"] if top else (c.reviewer.nickname if c.reviewer else None),
                average_score=avg_map.get(c.id),
            )
        )

    return result

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