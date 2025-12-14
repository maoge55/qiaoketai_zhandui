from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_db
from app.models import HomepageConfig
from app.schemas import HomepageConfigOut

router = APIRouter(prefix="/api", tags=["homepage"])


def _normalize_homepage_config(config: HomepageConfig) -> HomepageConfig:
    """Ensure JSON fields are lists for schema compatibility."""

    def to_list(val):
        if val is None:
            return []
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            return list(val.values())
        if isinstance(val, (str, int, float, bool)):
            return [val]
        return []

    config.banner_images = to_list(config.banner_images)
    config.featured_achievements = to_list(config.featured_achievements)
    config.featured_members = to_list(config.featured_members)
    config.arena_pool_versions = to_list(config.arena_pool_versions)
    return config


@router.get("/homepage", response_model=HomepageConfigOut)
def get_homepage_config(db: Session = Depends(get_db)):
    config = db.query(HomepageConfig).first()
    if not config:
        config = HomepageConfig(
            team_logo_url="/static/img/logo.png",
            banner_images=[],
            featured_achievements=[],
            featured_members=[],
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return _normalize_homepage_config(config)


@router.get("/arena-pool-versions", response_model=List[str])
def get_arena_pool_versions(db: Session = Depends(get_db)):
    """获取竞技场卡池版本列表（公共接口，前端筛选用）"""
    config = db.query(HomepageConfig).first()
    if not config or not config.arena_pool_versions:
        return []
    versions = config.arena_pool_versions
    if isinstance(versions, list):
        return versions
    return []
