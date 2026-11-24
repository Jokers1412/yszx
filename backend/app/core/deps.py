"""公共 FastAPI 依赖：DB/Redis 会话、双端登录态（04 §1.5）。

登录态：
  - 学员端 get_current_student / get_optional_student（游客边界见 04 §1.5 口径 S9）；
  - 管理端 get_current_admin 返回 AdminContext（含权限集）；
  - 学员 token 访问 /api/admin/*（反之亦然）→ 401（双端受众校验在 decode_token）。
"""
from typing import AsyncGenerator, Optional

import jwt as pyjwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.error_codes import ErrorCode
from app.core.context import ROLE_SUPER_ADMIN, AdminContext
from app.core.database import get_db
from app.core.exceptions import BizError
from app.core.redis import get_redis
from app.core.security import decode_token

_bearer = HTTPBearer(auto_error=False)


# ---------- 会话 ----------

__all__ = [
    "get_db",
    "get_redis",
    "get_token",
    "get_current_student",
    "get_optional_student",
    "get_current_admin",
    "StudentContext",
]


# ---------- 令牌提取 ----------

def get_token(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str:
    if credentials is None or not credentials.credentials:
        raise BizError(ErrorCode.AUTH_TOKEN_INVALID, "未登录或登录态失效", http_status=401)
    return credentials.credentials


def _decode_or_raise(token: str, audience: str, token_type: str = "access") -> dict:
    try:
        return decode_token(token, audience, token_type)  # type: ignore[arg-type]
    except pyjwt.ExpiredSignatureError:
        raise BizError(ErrorCode.AUTH_TOKEN_EXPIRED, "登录已过期，请重新登录", http_status=401)
    except pyjwt.PyJWTError:
        raise BizError(ErrorCode.AUTH_TOKEN_INVALID, "登录态无效，请重新登录", http_status=401)


# ---------- 学员端登录态 ----------

class StudentContext:
    def __init__(self, student_id: int, phone: str, nickname: str) -> None:
        self.student_id = student_id
        self.phone = phone
        self.nickname = nickname


async def get_current_student(
    request: Request,
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_db),
) -> StudentContext:
    payload = _decode_or_raise(token, "portal")
    student_id = int(payload["sub"])

    from app.modules.accounts.models import Student  # 延迟导入，保持 core 无模块依赖方向

    row = (
        await db.execute(
            select(Student).where(Student.id == student_id, Student.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if row is None:
        raise BizError(ErrorCode.AUTH_TOKEN_INVALID, "账号不存在或已注销", http_status=401)
    if row.status != 1:
        raise BizError(ErrorCode.AUTH_ACCOUNT_DISABLED, "账号已被禁用", http_status=403)

    ctx = StudentContext(row.id, row.phone, row.nickname)
    request.state.student_ctx = ctx
    return ctx


async def get_optional_student(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> Optional[StudentContext]:
    """游客可访问的接口用：无 token 返回 None，有 token 则校验。"""
    if credentials is None or not credentials.credentials:
        return None
    return await get_current_student(request, credentials.credentials, db)


# ---------- 管理端登录态 ----------

async def get_current_admin(
    request: Request,
    token: str = Depends(get_token),
    db: AsyncSession = Depends(get_db),
) -> AdminContext:
    payload = _decode_or_raise(token, "admin")
    admin_id = int(payload["sub"])

    from app.modules.system.models import AdminUser, Role, RolePermission

    row = (
        await db.execute(
            select(AdminUser).where(AdminUser.id == admin_id, AdminUser.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if row is None:
        raise BizError(ErrorCode.AUTH_TOKEN_INVALID, "账号不存在或已删除", http_status=401)
    if row.status != 1:
        raise BizError(ErrorCode.AUTH_ACCOUNT_DISABLED, "账号已被禁用", http_status=403)

    role = (
        await db.execute(
            select(Role).where(Role.id == row.role_id, Role.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if role is None:
        raise BizError(ErrorCode.PERM_DENIED, "角色不存在或已删除", http_status=403)

    is_super = role.code == ROLE_SUPER_ADMIN
    perm_codes: set[str] = set()
    if not is_super:
        perm_codes = set(
            (
                await db.execute(
                    select(RolePermission.permission_code).where(
                        RolePermission.role_id == role.id
                    )
                )
            ).scalars().all()
        )

    ctx = AdminContext(
        admin_id=row.id,
        username=row.username,
        role_code=role.code,
        is_super_admin=is_super,
        permission_codes=frozenset(perm_codes),
    )
    request.state.admin_ctx = ctx
    return ctx


async def get_super_admin(ctx: AdminContext = Depends(get_current_admin)) -> AdminContext:
    """仅超级管理员可用的依赖（04 Q3：角色管理接口仅超管）。"""
    if not ctx.is_super_admin:
        raise BizError(ErrorCode.PERM_DENIED, "仅超级管理员可执行该操作", http_status=403)
    return ctx
