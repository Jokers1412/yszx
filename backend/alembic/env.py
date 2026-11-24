"""Alembic 迁移环境（异步引擎，与应用共用配置）。

用法：
  alembic stamp head        # 首次：以 schema.sql 建好的库为基线打标记
  alembic revision --autogenerate -m "xxx"   # 后续结构变更（务必人工复核 diff）
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

from app.core.config import get_settings
from app.core.database import Base

# 导入全部业务模块模型，使 Base.metadata 完整（autogenerate 依赖）
from app.modules.accounts import models as _accounts_models  # noqa: F401
from app.modules.system import models as _system_models  # noqa: F401
from app.modules.content import models as _content_models  # noqa: F401
from app.modules.learning import models as _learning_models  # noqa: F401
from app.modules.interview import models as _interview_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
