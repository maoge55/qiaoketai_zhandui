import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ==== 关键：把项目根目录加入 sys.path ====
# env.py 位于 QIAOKETAI_ZHANDUI/alembic/env.py
# 根目录就是它的上一级
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ========================================

# 现在可以正常 import 我们自己的代码了
from app.config import settings
from app import models  # 确保执行 models.__init__，把所有模型注册到 Base.metadata

# 这个是 alembic.ini 中的配置对象
config = context.config

# 如果你不想搞 logging，就先别调用 fileConfig，避免报 'formatters' 错
# if config.config_file_name is not None:
#     fileConfig(config.config_file_name)

# 告诉 Alembic：要对比的元数据来自我们的 Base
target_metadata = models.Base.metadata


def run_migrations_offline():
    """Offline 模式：不真正连接数据库，只生成 SQL"""
    url = settings.SQLALCHEMY_DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,  # 字段类型变化也对比
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Online 模式：真正连数据库执行迁移"""
    # 从我们的 settings 里拿连接串
    config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URL)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
