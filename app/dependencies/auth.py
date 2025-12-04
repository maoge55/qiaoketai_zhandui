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
    }

    def dependency(user: User = Depends(get_current_user)) -> User:
        if role_order[user.role] < role_order[min_role]:
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
