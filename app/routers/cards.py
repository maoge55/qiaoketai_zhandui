from typing import List, Optional
import re

from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, func, case
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db, get_current_user_from_cookie
from app.models import Card, CardReview, User, UserProfile, ArenaCardStats
from app.schemas import CardOut

router = APIRouter(prefix="/api/cards", tags=["cards"])

@router.get("")
def list_cards(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_from_cookie),
    # 版本筛选（下拉框用）
    version: Optional[str] = Query(None, description="按 cards.version 过滤"),
    # 兼容老的 expansion 参数
    expansion: Optional[str] = Query(
        None, description="兼容老参数，按 expansion 过滤（可选）"
    ),
    # 竞技场卡池版本列表筛选
    arena_versions: Optional[str] = Query(
        None, description="按竞技场卡池版本过滤，逗号分隔的版本列表"
    ),
    # 职业筛选
    card_class: Optional[str] = Query(
        None, description="按职业过滤"
    ),
    # 稀有度筛选
    rarity: Optional[str] = Query(
        None, description="按稀有度过滤"
    ),
    # 已点评/未点评筛选（是否有任意用户点评过）
    has_reviews: Optional[bool] = Query(
        None, description="筛选有点评/无点评的卡牌"
    ),
    # 筛选当前用户是否点评过（仅当前登录用户）
    my_reviewed: Optional[bool] = Query(
        None, description="筛选当前用户点评过/未点评过的卡牌"
    ),
    # 模糊搜索
    search: Optional[str] = Query(
        None, description="模糊搜索卡牌名"
    ),
    sort_by: Optional[str] = Query(
        "win", description="排序字段：class|win|mana|score"
    ),
    sort_order: str = Query(
        "desc", regex="^(asc|desc)$", description="排序方向"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
):
    # 均分子查询：给"按评分"排序用
    avg_sub = (
        db.query(
            CardReview.card_id.label("cid"),
            func.avg(CardReview.score).label("avg_score"),
        )
        .group_by(CardReview.card_id)
        .subquery()
    )

    # 根据职业筛选决定从 arena_card_stats 取哪个职业的胜率
    # 如果选择了职业，取对应职业的数据；否则取"全部职业"的数据
    # 注意：中立卡牌没有职业胜率，统一使用"全部职业"的数据
    stats_class = "全部职业"  # 统一使用全部职业的胜率数据
    
    # 竞技场胜率子查询
    arena_stats_sub = (
        db.query(
            ArenaCardStats.card_id.label("cid"),
            ArenaCardStats.win_rate.label("arena_win_rate"),
            ArenaCardStats.popularity.label("arena_popularity"),
            ArenaCardStats.drawn_win_rate.label("arena_drawn_win_rate"),
            ArenaCardStats.played_win_rate.label("arena_played_win_rate"),
            ArenaCardStats.num_games.label("arena_num_games"),
        )
        .filter(ArenaCardStats.card_class == stats_class)
        .subquery()
    )

    query = (
        db.query(
            Card,
            avg_sub.c.avg_score.label("avg_score"),
            arena_stats_sub.c.arena_win_rate.label("arena_win_rate"),
            arena_stats_sub.c.arena_popularity.label("arena_popularity"),
            arena_stats_sub.c.arena_drawn_win_rate.label("arena_drawn_win_rate"),
            arena_stats_sub.c.arena_played_win_rate.label("arena_played_win_rate"),
            arena_stats_sub.c.arena_num_games.label("arena_num_games"),
        )
        .outerjoin(avg_sub, Card.id == avg_sub.c.cid)
        .outerjoin(arena_stats_sub, Card.card_id == arena_stats_sub.c.cid)
    )

    # 竞技场卡池筛选（优先级高于普通版本筛选）
    if arena_versions:
        versions_list = [v.strip() for v in arena_versions.split(",") if v.strip()]
        if versions_list:
            query = query.filter(Card.version.in_(versions_list))
    elif version:
        query = query.filter(Card.version == version)
    elif expansion:
        query = query.filter(Card.expansion == expansion)

    if card_class:
        query = query.filter(Card.card_class == card_class)

    if rarity:
        query = query.filter(Card.rarity == rarity)

    # 已点评/未点评筛选：是否有任意用户点评过
    if has_reviews is not None:
        if has_reviews:
            # 有点评：只要存在任意点评即可
            query = query.filter(Card.reviews.any())
        else:
            # 无点评：没有任何点评
            query = query.filter(~Card.reviews.any())

    # 当前用户是否点评过筛选
    if my_reviewed is not None and current_user:
        if my_reviewed:
            # 我点评过的：存在当前用户的点评
            query = query.filter(Card.reviews.any(CardReview.reviewer_id == current_user.id))
        else:
            # 我未点评的：不存在当前用户的点评
            query = query.filter(~Card.reviews.any(CardReview.reviewer_id == current_user.id))

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
        # 使用 arena_card_stats 表的胜率
        query = query.order_by(nulls_last(arena_stats_sub.c.arena_win_rate), direction(arena_stats_sub.c.arena_win_rate), Card.name.asc())
    elif sort_by == "score":
        query = query.order_by(nulls_last(avg_sub.c.avg_score), direction(avg_sub.c.avg_score), Card.name.asc())
    else:  # 默认按水晶排序
        query = query.order_by(direction(Card.mana_cost), Card.name.asc())

    # 先获取总数（在分页之前）
    total = query.count()

    rows = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    cards = []
    avg_map: dict[int, float | None] = {}
    win_rate_map: dict[int, float | None] = {}
    for row in rows:
        # row: (Card, avg_score, arena_win_rate, arena_popularity, ...)
        card = row[0]
        avg_score = row[1]
        arena_win_rate = row[2]
        cards.append(card)
        if avg_score is not None:
            avg_map[card.id] = float(avg_score)
        if arena_win_rate is not None:
            win_rate_map[card.id] = float(arena_win_rate)

    # 补充点评均分
    card_ids = [c.id for c in cards]
    top_map = {}

    if card_ids:
        # 取点赞数最高的点评（若点赞数为空则排在后面），用于列表页展示点评人和短评
        upvote_null_last = case((CardReview.upvote_count.is_(None), 1), else_=0)
        top_reviews = (
            db.query(
                CardReview.card_id,
                CardReview.content,
                User.nickname.label("nick"),
                User.username.label("uname"),
                CardReview.upvote_count,
                CardReview.created_at,
            )
            .join(User, User.id == CardReview.reviewer_id)
            .outerjoin(UserProfile, UserProfile.user_id == User.id)
            .filter(CardReview.card_id.in_(card_ids))
            .order_by(upvote_null_last, CardReview.upvote_count.desc(), CardReview.created_at.desc())
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

    # 构造响应模型
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
                arena_score=c.arena_score,  # 保持原来的评分数据
                arena_win_rates=c.arena_win_rates,
                short_review=top["content"] if top else c.short_review,
                reviewer_nickname=top["reviewer"] if top else (c.reviewer.nickname if c.reviewer else None),
                average_score=avg_map.get(c.id),
                hdt_win_rate=win_rate_map.get(c.id),  # HDT 竞技场胜率
            )
        )

    # 返回带分页信息的响应
    return {
        "items": result,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@router.get("/expansions", response_model=List[str])
def list_versions(db: Session = Depends(get_db)):
    """
    下拉框用的版本列表：
    - 实际返回的是 cards.version
    - 排序规则：按 expansion 中 () 里的年份倒序（新的在前）
    """
    rows = db.query(distinct(Card.version), Card.expansion).all()

    items = []
    for version, expansion in rows:
        if not version:
            continue

        year = 0
        if expansion:
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

    items.sort(key=lambda x: (x["year"], x["version"]), reverse=True)
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
