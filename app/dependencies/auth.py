from typing import Optional, Callable

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User, UserRole
from app.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    token_data = decode_access_token(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的 token",
        )
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    return user


async def get_current_user_from_cookie(
    request: Request, db: Session = Depends(get_db)
) -> Optional[User]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    token_data = decode_access_token(token)
    if not token_data:
        return None
    return db.query(User).filter(User.id == token_data.user_id).first()


def require_role(min_role: UserRole) -> Callable:
    role_order = {
        UserRole.VISITOR: 0,
        UserRole.USER: 1,
        UserRole.MEMBER: 2,
        UserRole.ELITE_MEMBER: 3,
        UserRole.ADMIN: 4,
        UserRole.SUPER_ADMIN: 5,
    }

    def dependency(user: User = Depends(get_current_user)) -> User:
        # 兼容旧数据：如果数据库里是 admin 但代码里没 super_admin，这里不会报错
        # 但如果 min_role 是 super_admin，普通 admin 就会被拦住
        user_level = role_order.get(user.role, 0)
        required_level = role_order.get(min_role, 0)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return user

    return dependency


def require_member(user: User = Depends(require_role(UserRole.MEMBER))):
    return user


def require_elite_member(
    user: User = Depends(require_role(UserRole.ELITE_MEMBER)),
):
    return user


def require_admin(user: User = Depends(require_role(UserRole.ADMIN))):
    return user


# ========== 支持 Cookie 认证的角色检查 ==========

async def get_current_user_from_cookie_required(
    request: Request, db: Session = Depends(get_db)
) -> User:
    """从 cookie 获取当前用户，如果没有则抛出 401"""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录",
        )
    token_data = decode_access_token(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的 token",
        )
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    return user


def require_role_cookie(min_role: UserRole) -> Callable:
    """基于 cookie 认证的角色检查"""
    role_order = {
        UserRole.VISITOR: 0,
        UserRole.USER: 1,
        UserRole.MEMBER: 2,
        UserRole.ELITE_MEMBER: 3,
        UserRole.ADMIN: 4,
        UserRole.SUPER_ADMIN: 5,
    }

    async def dependency(
        request: Request, db: Session = Depends(get_db)
    ) -> User:
        user = await get_current_user_from_cookie_required(request, db)
        user_level = role_order.get(user.role, 0)
        required_level = role_order.get(min_role, 0)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return user

    return dependency


async def require_admin_cookie(
    request: Request, db: Session = Depends(get_db)
) -> User:
    """基于 cookie 认证的管理员权限检查"""
    dep = require_role_cookie(UserRole.ADMIN)
    return await dep(request, db)
