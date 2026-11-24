"""system 数据模型（03 §2.1 admin_user/role/role_permission/system_setting/operation_log）。

- role_permission 编辑=事务内物理替换（无 deleted_at，03 §3.2 编辑替换类）；
- system_setting 固定单行 id=1（R1 后为自增主键）；
- operation_log 追加只增+清空=批量逻辑删除。
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Computed, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class AdminUser(Base, TimestampMixin):
    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50))
    password_hash: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(11))
    email: Mapped[Optional[str]] = mapped_column(String(100))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(255))
    role_id: Mapped[int] = mapped_column(BigInteger)  # 逻辑关联 role.id
    status: Mapped[int] = mapped_column(Integer, default=1)
    last_login_at: Mapped[Optional[datetime]] = mapped_column()
    deleted_at: Mapped[Optional[datetime]] = mapped_column()
    username_uk: Mapped[Optional[str]] = mapped_column(
        String(50), Computed("IF(deleted_at IS NULL, username, NULL)", persisted=False),
        unique=True,
    )
    phone_uk: Mapped[Optional[str]] = mapped_column(
        String(11), Computed("IF(deleted_at IS NULL, phone, NULL)", persisted=False),
        unique=True,
    )


class Role(Base, TimestampMixin):
    __tablename__ = "role"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(String(255))
    is_preset: Mapped[int] = mapped_column(Integer, default=0)  # 1预置（禁删）0自建
    deleted_at: Mapped[Optional[datetime]] = mapped_column()
    code_uk: Mapped[Optional[str]] = mapped_column(
        String(50), Computed("IF(deleted_at IS NULL, code, NULL)", persisted=False),
        unique=True,
    )


class RolePermission(Base):
    __tablename__ = "role_permission"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(BigInteger)  # 逻辑关联 role.id
    permission_code: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(server_default="CURRENT_TIMESTAMP")


class SystemSetting(Base):
    __tablename__ = "system_setting"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    platform_name: Mapped[str] = mapped_column(String(50), default="云枢智学")
    platform_description: Mapped[Optional[str]] = mapped_column(String(500))
    logo_url: Mapped[Optional[str]] = mapped_column(String(255))
    default_avatar_url: Mapped[Optional[str]] = mapped_column(String(255))
    good_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("98.00"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class OperationLog(Base):
    __tablename__ = "operation_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    admin_username: Mapped[Optional[str]] = mapped_column(String(50))
    action_type: Mapped[int] = mapped_column(Integer)  # 1登录 2新增 3修改 4删除 5禁用 6其他
    action_desc: Mapped[str] = mapped_column(String(200))
    target: Mapped[Optional[str]] = mapped_column(String(200))
    detail: Mapped[Optional[str]] = mapped_column(String(500))
    ip: Mapped[str] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(server_default="CURRENT_TIMESTAMP")
    deleted_at: Mapped[Optional[datetime]] = mapped_column()
