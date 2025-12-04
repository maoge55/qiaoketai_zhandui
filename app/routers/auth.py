from datetime import datetime, timedelta
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.dependencies.auth import get_db, get_current_user
from app.models import User, UserProfile, EmailVerificationCode, UserRole
from app.schemas import (
    UserRegister,
    UserLogin,
    UserBase,
    Token,
    SendVerificationCodeRequest,
)
from app.utils.security import get_password_hash, verify_password, create_access_token
from app.utils.email import send_email_qq
from app.config import settings
import random,hashlib 
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/send_verification_code")
def send_verification_code(
    payload: SendVerificationCodeRequest, db: Session = Depends(get_db)
):
    email = payload.email
    code = f"{random.randint(100000, 999999)}"

    expires_at = datetime.utcnow() + timedelta(minutes=10)

    db.query(EmailVerificationCode).filter(
        EmailVerificationCode.email == email,
        EmailVerificationCode.used == False,
    ).update({"used": True})

    db_code = EmailVerificationCode(
        email=email,
        code=code,
        expires_at=expires_at,
        used=False,
    )
    db.add(db_code)
    db.commit()

    subject = "【敲可爱战队】邮箱验证码"
    body = f"您的验证码是：{code}，10 分钟内有效。请勿泄露给他人。"
    ok = send_email_qq(email, subject, body)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="验证码发送失败，请稍后再试",
        )
    return {"message": "验证码已发送"}


@router.post("/register", response_model=UserBase)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    # 检查验证码
    code_row = (
        db.query(EmailVerificationCode)
        .filter(
            EmailVerificationCode.email == payload.email,
            EmailVerificationCode.code == payload.verification_code,
            EmailVerificationCode.used == False,
            EmailVerificationCode.expires_at > datetime.utcnow(),
        )
        .first()
    )
    if not code_row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码无效或已过期",
        )

    # 检查用户名 & 邮箱唯一
    if (
        db.query(User)
        .filter(
            (User.username == payload.username)
            | (User.email == payload.email)
        )
        .first()
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名或邮箱已存在",
        )

    # 注意：后端只接收 password_md5，当成真正的“密码原文”进行 bcrypt 哈希
    password_hash = get_password_hash(payload.password_md5)

    # ===== 根据邮箱 / 会员码决定角色 =====
    role = UserRole.USER  # 默认普通用户

    # 1. 特殊邮箱：强制管理员优先级最高
    if settings.ADMIN_EMAIL and payload.email == settings.ADMIN_EMAIL:
        role = UserRole.ADMIN
    else:
        # 2. 如果有会员码 md5，根据 .env 里的明文会员码计算 md5 比较
        if payload.membership_code_md5:
            def md5_of(raw: str) -> str:
                return hashlib.md5(raw.encode("utf-8")).hexdigest()

            code_md5 = payload.membership_code_md5

            # 管理员码
            if settings.QK_ADMIN_CODE and code_md5 == md5_of(settings.QK_ADMIN_CODE):
                role = UserRole.ADMIN
            # 精英成员码
            elif settings.QK_ELITE_MEMBER_CODE and code_md5 == md5_of(settings.QK_ELITE_MEMBER_CODE):
                role = UserRole.ELITE_MEMBER
            # 普通成员码
            elif settings.QK_MEMBER_CODE and code_md5 == md5_of(settings.QK_MEMBER_CODE):
                role = UserRole.MEMBER
    # ====================================

    user = User(
        username=payload.username,
        nickname=payload.nickname,
        email=payload.email,
        password_hash=password_hash,
        role=role,
    )

    db.add(user)
    db.flush()  # 获取 user.id

    profile = UserProfile(user_id=user.id)
    db.add(profile)

    code_row.used = True
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=Token)
def login(
    payload: UserLogin, response: Response, db: Session = Depends(get_db)
):
    # 前端按「用户名前三位 + 明文密码」取 md5，后端只知道 md5 结果
    user = (
        db.query(User)
        .filter(
            (User.username == payload.username_or_email)
            | (User.email == payload.username_or_email)
        )
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账号不存在",
        )

    if not verify_password(payload.password_md5, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码错误",
        )

    token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )

    # 按需求：保存 JWT 到前端，并刷新用户信息到 cookie
    # 这里后端设置一个可被 JS 访问的 cookie（非 HttpOnly）
    # access token cookie: use seconds for max_age
    access_token_max_age = int(timedelta(minutes=15).total_seconds())
    response.set_cookie(
        "access_token", str(token), max_age=access_token_max_age, httponly=True
    )
    response.set_cookie(
        key="user_role",
        value=user.role.value,
        httponly=False,
        max_age=60 * 60 * 24,
        path="/",
    )
    # Percent-encode nickname so non-ASCII characters don't break cookie encoding
    nickname_for_cookie = quote(user.nickname or "")
    response.set_cookie(
        key="user_nickname",
        value=nickname_for_cookie,
        httponly=False,
        max_age=60 * 60 * 24,
        path="/",
    )

    return Token(access_token=token)


@router.get("/me", response_model=UserBase)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/resolve_username")
def resolve_username(payload: dict, db: Session = Depends(get_db)):
    """给前端：当用户在登录框输入的是邮箱时，前端可以调用此接口获取对应的用户名以用于计算 md5 前缀。"""
    identifier = payload.get("email_or_username")
    if not identifier:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少 identifier")

    user = (
        db.query(User)
        .filter((User.username == identifier) | (User.email == identifier))
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return {"username": user.username}


@router.post("/logout")
def logout(response: Response):
    # 清空后端设置的 cookies（包含 HttpOnly 的 access_token）
    response.set_cookie("access_token", "", max_age=0, httponly=True, path="/")
    response.set_cookie("user_role", "", httponly=False, max_age=0, path="/")
    response.set_cookie("user_nickname", "", httponly=False, max_age=0, path="/")
    return {"message": "已登出"}
