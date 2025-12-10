from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SQLALCHEMY_DATABASE_URL: str

    JWT_SECRET_KEY: str = "change_me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 365  # 1 年

    EMAIL_SENDER: str
    EMAIL_PASSWORD: str
    EMAIL_SMTP_SERVER: str = "smtp.qq.com"
    EMAIL_SMTP_PORT: int = 465
    EMAIL_SENDER_NAME: str = "敲可爱官方"

    # ==== 新增：会员码 & 管理员邮箱 ====
    QK_MEMBER_CODE: str | None = None        # qkann -> 普通成员
    QK_ELITE_MEMBER_CODE: str | None = None  # alinb -> elite_member
    QK_ADMIN_CODE: str | None = None         # myadminqka -> admin
    ADMIN_EMAIL: str | None = None           # 1126642524@qq.com 注册即 admin

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
