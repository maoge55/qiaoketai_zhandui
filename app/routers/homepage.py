from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db
from app.models import HomepageConfig
from app.schemas import HomepageConfigOut

router = APIRouter(prefix="/api", tags=["homepage"])


@router.get("/homepage", response_model=HomepageConfigOut)
def get_homepage_config(db: Session = Depends(get_db)):
    config = db.query(HomepageConfig).first()
    if not config:
        config = HomepageConfig(
            team_logo_url="/static/img/logo.png",
            banner_images=[],
            featured_achievements={},
            featured_members={},
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config
