from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import distinct
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db
from app.models import Card
from app.schemas import CardOut

router = APIRouter(prefix="/api/cards", tags=["cards"])


@router.get("", response_model=List[CardOut])
def list_cards(
    expansion: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    query = db.query(Card)
    if expansion:
        query = query.filter(Card.expansion == expansion)
    query = query.order_by(Card.mana_cost.asc(), Card.name.asc())
    cards = query.offset((page - 1) * page_size).limit(page_size).all()
    return cards


@router.get("/expansions", response_model=List[str])
def list_expansions(db: Session = Depends(get_db)):
    expansions = db.query(distinct(Card.expansion)).all()
    return [e[0] for e in expansions]
