"""accounts 数据模型（03 §2.1.1 student 表）。

禁物理外键；逻辑删除 deleted_at；*_uk 为「活动行唯一生成列」（03 §2 约定）。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Computed, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class Student(Base, TimestampMixin):
    __tablename__ = "student"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(11))
    password_hash: Mapped[str] = mapped_column(String(100))
    nickname: Mapped[str] = mapped_column(String(50))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(100))
    gender: Mapped[int] = mapped_column(Integer, default=2)  # 0男 1女 2保密
    status: Mapped[int] = mapped_column(Integer, default=1)  # 1启用 0禁用
    last_login_at: Mapped[Optional[datetime]] = mapped_column()
    deleted_at: Mapped[Optional[datetime]] = mapped_column()
    phone_uk: Mapped[Optional[str]] = mapped_column(
        String(11), Computed("IF(deleted_at IS NULL, phone, NULL)", persisted=False), unique=True
    )
