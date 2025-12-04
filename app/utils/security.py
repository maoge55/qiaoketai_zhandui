from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings
from app.schemas import TokenData
from app.models import UserRole

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _normalize_password(p: str | bytes) -> str:
    """统一处理一下密码字符串，避免 bcrypt 报错"""
    if p is None:
        raise ValueError("Password is required")
    if isinstance(p, bytes):
        p = p.decode("utf-8", errors="ignore")
    # bcrypt 只支持前 72 字节，这里简单截断一下（我们现在实际是 32 字符的 md5）
    if len(p) > 72:
        p = p[:72]
    return p


def get_password_hash(plain_password: str | bytes) -> str:
    """
    这里的 plain_password 实际上传进来的就是前端算好的 password_md5
    """
    plain_password = _normalize_password(plain_password)
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str | bytes, hashed_password: str) -> bool:
    """
    登陆时验证密码，同样对传入密码做统一处理
    """
    plain_password = _normalize_password(plain_password)
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(
    user_id: int,
    username: str,
    role: UserRole,
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = {
        "sub": username,
        "user_id": user_id,
        "role": role.value,  # 确保传递的是枚举的值（'admin', 'user' 等）
    }
    expire = datetime.utcnow() + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    # 确保返回的 token 是字符串类型
    if isinstance(encoded_jwt, bytes):
        encoded_jwt = encoded_jwt.decode('utf-8')
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenData(
            user_id=payload.get("user_id"),
            username=payload.get("sub"),
            role=UserRole(payload.get("role")),
        )
    except JWTError:
        return None
