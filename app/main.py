from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import engine
from app.models import Base
from app.routers import (
    auth as auth_router,
    articles as articles_router,
    comments as comments_router,
    cards as cards_router,
    members as members_router,
    achievements as achievements_router,
    admin as admin_router,
    homepage as homepage_router,
    pages as pages_router,
)

# 确保建表（生产推荐用 Alembic 迁移）
Base.metadata.create_all(bind=engine)

app = FastAPI(title="敲可爱战队 - 炉石竞技场战队官网", version="0.1.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# API 路由
app.include_router(auth_router.router)
app.include_router(articles_router.router)
app.include_router(comments_router.router)
app.include_router(cards_router.router)
app.include_router(members_router.router)
app.include_router(achievements_router.router)
app.include_router(admin_router.router)
app.include_router(homepage_router.router)

# 页面路由
app.include_router(pages_router.router)
