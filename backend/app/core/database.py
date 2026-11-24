"""SQLAlchemy 2.x 异步数据访问层。

约定（docs/rules/database-rules.md / 02 §2.2）：
  - 自增主键 id BIGINT；禁止物理外键；逻辑删除 deleted_at IS NULL=有效；
  - 时间列 DATETIME（naive UTC，连接时区 UTC）；展示层转 Asia/Shanghai（D9）。
"""
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import MetaData, func
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

# 命名约定（Alembic 迁移友好）
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uk_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    metadata = metadata


engine: AsyncEngine = create_async_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：每请求一个 AsyncSession。"""
    async with SessionLocal() as session:
        yield session


class TimestampMixin:
    """公共时间列（UTC；updated_at 由 ORM onupdate 维护，DB 侧同有 ON UPDATE）。"""

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
