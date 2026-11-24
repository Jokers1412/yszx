"""system 路由（admin 挂载于 /api/admin/v1；public_router 挂载于 /api/portal/v1）。

已实现（04 §4.1/§4.9/§4.10/§4.11/§4.12 + §3.2）：
  认证：POST /auth/login | POST /auth/logout | GET /auth/profile
  用户管理（user:*）：/users 列表/详情/新增/编辑/删除/批量删除/启停/批量启停/重置密码
  角色管理（仅超管，Q3）：/roles 列表/新增/编辑/权限/删除 + GET /permissions
  操作日志（log:view / system:settings 归并）：/logs 列表/详情/导出 CSV/清空
  系统设置（system:settings）：GET/PUT /settings + POST /settings/upload
  公开配置（游客）：GET /settings/public（public_router，两端共用）
"""
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.core.context import AdminContext
from app.core.database import get_db
from app.core.deps import get_current_admin, get_super_admin
from app.core.rbac import require_perm
from app.core.redis import get_redis
from app.core.response import ok
from app.core import storage
from app.modules.system import service
from app.modules.system.schemas import (
    BatchIds,
    BatchStatusPatch,
    LogQuery,
    LoginRequest,
    LogoutRequest,
    RoleCreate,
    RolePermissionsUpdate,
    RoleUpdate,
    SettingsUpdate,
    UserCreate,
    UserQuery,
    UserStatusPatch,
    UserUpdate,
)

router = APIRouter(tags=["system"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


# ===================== 认证（04 §4.1） =====================

@router.post("/auth/login")
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """后台登录（游客｜频控✓）。"""
    result = await service.login(db, r, payload, ip=_client_ip(request))
    return ok(result.model_dump())


@router.post("/auth/logout")
async def logout(
    request: Request,
    payload: LogoutRequest | None = None,
    ctx: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """登出：refresh 立即失效，记操作日志。"""
    refresh = payload.refreshToken if payload else None
    result = await service.logout(db, r, ctx, refresh, ip=_client_ip(request))
    return ok(result)


@router.get("/auth/profile")
async def profile(
    ctx: AdminContext = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """当前管理员 + 权限码集合。"""
    result = await service.get_profile(db, ctx)
    return ok(result.model_dump())


# ===================== 用户管理（04 §4.9） =====================

@router.get("/users")
async def list_users(
    q: UserQuery = Depends(),
    _ctx: AdminContext = Depends(require_perm("user:view")),
    db: AsyncSession = Depends(get_db),
):
    result = await service.list_users(db, q)
    return ok(result.model_dump())


@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    _ctx: AdminContext = Depends(require_perm("user:view")),
    db: AsyncSession = Depends(get_db),
):
    result = await service.get_user_detail(db, user_id)
    return ok(result.model_dump())


@router.post("/users")
async def create_user(
    payload: UserCreate,
    request: Request,
    ctx: AdminContext = Depends(require_perm("user:create")),
    db: AsyncSession = Depends(get_db),
):
    result = await service.create_user(db, ctx, payload, ip=_client_ip(request))
    return ok(result, status_code=201)


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    ctx: AdminContext = Depends(require_perm("user:edit")),
    db: AsyncSession = Depends(get_db),
):
    result = await service.update_user(db, ctx, user_id, payload, ip=_client_ip(request))
    return ok(result)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
    ctx: AdminContext = Depends(require_perm("user:edit")),  # 删除归并 user:edit（V3）
    db: AsyncSession = Depends(get_db),
):
    result = await service.delete_users(db, ctx, BatchIds(ids=[user_id]), ip=_client_ip(request))
    return ok(result)


@router.post("/users/batch-delete")
async def batch_delete_users(
    payload: BatchIds,
    request: Request,
    ctx: AdminContext = Depends(require_perm("user:edit")),
    db: AsyncSession = Depends(get_db),
):
    result = await service.delete_users(db, ctx, payload, ip=_client_ip(request))
    return ok(result)


@router.patch("/users/{user_id}/status")
async def patch_user_status(
    user_id: int,
    payload: UserStatusPatch,
    request: Request,
    ctx: AdminContext = Depends(require_perm("user:disable")),
    db: AsyncSession = Depends(get_db),
):
    result = await service.patch_user_status(
        db, ctx, BatchIds(ids=[user_id]), payload.status, ip=_client_ip(request)
    )
    return ok(result)


@router.post("/users/batch-status")
async def batch_user_status(
    payload: BatchStatusPatch,
    request: Request,
    ctx: AdminContext = Depends(require_perm("user:disable")),
    db: AsyncSession = Depends(get_db),
):
    result = await service.patch_user_status(
        db, ctx, BatchIds(ids=payload.ids), payload.status, ip=_client_ip(request)
    )
    return ok(result)


@router.post("/users/{user_id}/password-reset")
async def reset_user_password(
    user_id: int,
    request: Request,
    ctx: AdminContext = Depends(require_perm("user:edit")),  # 重置密码归并 user:edit（V3）
    db: AsyncSession = Depends(get_db),
):
    result = await service.reset_user_password(db, ctx, user_id, ip=_client_ip(request))
    return ok(result)


# ===================== 角色管理（04 §4.10，仅超管） =====================

@router.get("/roles")
async def list_roles(
    _ctx: AdminContext = Depends(get_super_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await service.list_roles(db)
    return ok(result)


@router.post("/roles")
async def create_role(
    payload: RoleCreate,
    request: Request,
    ctx: AdminContext = Depends(get_super_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await service.create_role(db, ctx, payload, ip=_client_ip(request))
    return ok(result, status_code=201)


@router.put("/roles/{role_id}")
async def update_role(
    role_id: int,
    payload: RoleUpdate,
    request: Request,
    ctx: AdminContext = Depends(get_super_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await service.update_role(db, ctx, role_id, payload, ip=_client_ip(request))
    return ok(result)


@router.put("/roles/{role_id}/permissions")
async def update_role_permissions(
    role_id: int,
    payload: RolePermissionsUpdate,
    request: Request,
    ctx: AdminContext = Depends(get_super_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await service.update_role_permissions(db, ctx, role_id, payload, ip=_client_ip(request))
    return ok(result)


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int,
    request: Request,
    ctx: AdminContext = Depends(get_super_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await service.delete_role(db, ctx, role_id, ip=_client_ip(request))
    return ok(result)


@router.get("/permissions")
async def get_permissions(
    _ctx: AdminContext = Depends(get_super_admin),
):
    """权限树（04 附录 A：9 组 33 项）。"""
    return ok(service.permission_tree())


# ===================== 操作日志（04 §4.11） =====================

@router.get("/logs")
async def list_logs(
    q: LogQuery = Depends(),
    _ctx: AdminContext = Depends(require_perm("log:view")),
    db: AsyncSession = Depends(get_db),
):
    result = await service.list_logs(db, q)
    return ok(result.model_dump())


@router.get("/logs/export")
async def export_logs(
    request: Request,
    q: LogQuery = Depends(),
    ctx: AdminContext = Depends(require_perm("log:view")),
    db: AsyncSession = Depends(get_db),
):
    filename, data = await service.export_logs_csv(db, ctx, q, ip=_client_ip(request))
    return StreamingResponse(
        iter([data]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/logs/{log_id}")
async def get_log(
    log_id: int,
    _ctx: AdminContext = Depends(require_perm("log:view")),
    db: AsyncSession = Depends(get_db),
):
    result = await service.get_log(db, log_id)
    return ok(result.model_dump())


@router.delete("/logs")
async def clear_logs(
    request: Request,
    ctx: AdminContext = Depends(require_perm("system:settings")),  # 清空归并 system:settings（V3）
    db: AsyncSession = Depends(get_db),
):
    result = await service.clear_logs(db, ctx, ip=_client_ip(request))
    return ok(result)


# ===================== 系统设置（04 §4.12） =====================

@router.get("/settings")
async def get_settings(
    _ctx: AdminContext = Depends(require_perm("system:settings")),
    db: AsyncSession = Depends(get_db),
):
    result = await service.get_system_settings(db)
    return ok(result.model_dump())


@router.put("/settings")
async def save_settings(
    payload: SettingsUpdate,
    request: Request,
    ctx: AdminContext = Depends(require_perm("system:settings")),
    db: AsyncSession = Depends(get_db),
):
    result = await service.save_system_settings(db, ctx, payload, ip=_client_ip(request))
    return ok(result)


@router.post("/settings/upload")
async def upload_setting_image(
    request: Request,
    file: UploadFile = File(...),
    type: str = Form(..., pattern="^(logo|defaultAvatar)$"),
    ctx: AdminContext = Depends(require_perm("system:settings")),
    db: AsyncSession = Depends(get_db),
):
    """上传图片（jpg/png ≤2MB）→ { url }（04 §4.12，存 MinIO 02 D15）。"""
    from app.common.enums import OperationActionType

    data = await file.read()
    url = storage.upload_image(data, file.content_type or "", subdir="settings")
    from app.core.audit import record_operation

    await record_operation(
        db,
        action_type=OperationActionType.CREATE,
        action_desc="上传图片",
        target="Logo" if type == "logo" else "默认头像",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=_client_ip(request),
    )
    await db.commit()
    return ok({"url": url})


# ===================== 学员端公开配置（04 §3.2，挂载于 /api/portal/v1） =====================

public_router = APIRouter(tags=["system"])


@public_router.get("/settings/public")
async def get_public_settings(db: AsyncSession = Depends(get_db)):
    """平台公开配置（游客）：平台名称/描述/Logo/默认头像（两端共用）。"""
    return ok(await service.get_public_settings(db))
