"""system 业务服务（04 §4.1 认证；其余用户/角色/日志/设置待功能开发）。

登录规则（04 §4.1 / §1.5 / §1.7）：
  - 仅 admin_user 账号（学员账号不可登录管理端，C3）；
  - 失败锁定同 §1.7（连续 5 次密码错误锁 5 分钟，423 AUTH_LOCKED 提示剩余分钟）；
  - 双端 JWT 独立（aud=admin）；rememberMe → refresh 30d/7d；
  - 登录/登出入操作日志（B5，core.audit）；登出后该 refresh 立即失效。
"""
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.common import constants as C
from app.common.enums import OperationActionType
from app.common.error_codes import ErrorCode
from app.core import security
from app.core.audit import record_operation
from app.core.config import get_settings
from app.core.context import AdminContext
from app.core.exceptions import BizError
from app.core.rbac import PERMISSION_CODES, PERMISSION_TREE
from app.core.redis import get_redis
from app.core.ratelimit import (
    check_ip_account_limit,
    check_login_locked,
    clear_login_fail,
    record_login_fail,
)
from app.modules.system.models import AdminUser, OperationLog, Role, RolePermission, SystemSetting
from app.modules.system.schemas import (
    AdminUserBrief,
    LoginRequest,
    LoginResult,
    ProfileResult,
)


def _lock_key(username: str) -> str:
    return f"admin:{username}"


async def _load_role(db: AsyncSession, role_id: int) -> Role:
    role = (
        await db.execute(select(Role).where(Role.id == role_id, Role.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if role is None:
        raise BizError(ErrorCode.PERM_DENIED, "角色不存在或已删除", http_status=403)
    return role


def _brief(user: AdminUser, role: Role) -> AdminUserBrief:
    return AdminUserBrief(
        id=user.id,
        username=user.username,
        nickname=user.username,  # 派生值：admin_user 无 nickname 列（04 §4.1 契约字段）
        avatarUrl=user.avatar_url,
        roleName=role.name,
        isSuper=role.code == "super_admin",
    )


async def login(
    db: AsyncSession,
    r: aioredis.Redis,
    payload: LoginRequest,
    ip: str,
) -> LoginResult:
    settings = get_settings()

    # 频控（IP + 账号双维度，04 §1.7）
    await check_ip_account_limit(
        r, "admin_login", ip, payload.username, settings.rate_limit_login_per_minute
    )
    # 失败锁定检查（423 AUTH_LOCKED）
    await check_login_locked(r, _lock_key(payload.username))

    user = (
        await db.execute(
            select(AdminUser).where(
                AdminUser.username == payload.username,
                AdminUser.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()

    # 凭证校验（账号不存在与密码错误同文案，不泄露账号是否存在）
    if user is None or not security.verify_password(payload.password, user.password_hash):
        if user is not None:
            await record_login_fail(r, _lock_key(payload.username))
        raise BizError(ErrorCode.AUTH_INVALID_CREDENTIALS, "账号或密码错误", http_status=401)

    if user.status != 1:
        raise BizError(ErrorCode.AUTH_ACCOUNT_DISABLED, "账号已被禁用", http_status=403)

    # 登录成功：清零失败计数、更新登录时间
    await clear_login_fail(r, _lock_key(payload.username))
    await db.execute(
        update(AdminUser)
        .where(AdminUser.id == user.id)
        .values(last_login_at=datetime.now(timezone.utc).replace(tzinfo=None))
    )

    role = await _load_role(db, user.role_id)

    # 双 token（aud=admin，04 §1.5）
    access = security.create_access_token(str(user.id), "admin")
    refresh, _ttl = security.create_refresh_token(str(user.id), "admin", remember=payload.rememberMe)

    await record_operation(
        db,
        action_type=OperationActionType.LOGIN,
        action_desc="登录",
        admin_user_id=user.id,
        admin_username=user.username,
        ip=ip or "",
    )
    await db.commit()

    return LoginResult(
        accessToken=access,
        refreshToken=refresh,
        expiresIn=settings.jwt_access_ttl_minutes * 60,
        user=_brief(user, role),
    )


async def logout(
    db: AsyncSession,
    r: aioredis.Redis,
    ctx: AdminContext,
    refresh_token: str | None,
    ip: str,
) -> dict:
    # 该 refresh 立即失效（04 §4.1/§1.5；标记保留至 token 自然过期）
    if refresh_token:
        settings = get_settings()
        max_ttl = settings.jwt_refresh_ttl_days_remember * 24 * 3600
        await r.set(
            security.refresh_revoke_key("admin", refresh_token), "1", ex=max_ttl
        )

    await record_operation(
        db,
        action_type=OperationActionType.LOGIN,
        action_desc="登出",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip or "",
    )
    await db.commit()
    return {"success": True}


async def get_profile(db: AsyncSession, ctx: AdminContext) -> ProfileResult:
    user = (
        await db.execute(
            select(AdminUser).where(AdminUser.id == ctx.admin_id, AdminUser.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if user is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "账号不存在或已删除", http_status=404)
    role = await _load_role(db, user.role_id)

    # 超管返回全量 33 码（04 §4.1）
    codes = sorted(PERMISSION_CODES) if ctx.is_super_admin else sorted(ctx.permission_codes)
    return ProfileResult(user=_brief(user, role), permissionCodes=codes)


def permission_tree() -> list[dict]:
    """GET /permissions 权限树数据源（04 附录 A，9 组 33 项）——角色管理页用。"""
    return [
        {"group": group, "items": [{"code": code, "name": name} for code, name in items]}
        for group, items in PERMISSION_TREE
    ]


# ============================================================
# 用户管理（04 §4.9）
# ============================================================

from datetime import datetime as _dt, time as _time, timedelta  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

from sqlalchemy import func, or_  # noqa: E402

from app.common.enums import EnableStatus, OperationActionType  # noqa: E402
from app.common.pagination import PageResult  # noqa: E402
from app.common.utils import to_shanghai  # noqa: E402
from app.modules.system.schemas import (  # noqa: E402
    BatchIds,
    LogDetail,
    LogItem,
    LogQuery,
    RoleCreate,
    RoleItem,
    RolePermissionsUpdate,
    RoleUpdate,
    SettingsResult,
    SettingsUpdate,
    UserCreate,
    UserDetail,
    UserQuery,
    UserRecentLog,
    UserStatusPatch,
    UserUpdate,
)

_CN_TZ = ZoneInfo("Asia/Shanghai")

# 权限码 → （组名·权限名）快速索引
_PERM_LABELS: dict[str, tuple[str, str]] = {
    code: (group, name) for group, items in PERMISSION_TREE for code, name in items
}


def _status_str(value: int) -> str:
    return "enabled" if value == 1 else "disabled"


def _user_item(user: AdminUser, role: Role) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.username,  # 派生值（admin_user 无 nickname 列）
        "avatarUrl": user.avatar_url,
        "phone": user.phone,
        "roleCode": role.code,
        "roleName": role.name,
        "status": _status_str(user.status),
        "lastLoginAt": to_shanghai(user.last_login_at),
    }


async def _require_role_by_code(db: AsyncSession, role_code: str) -> Role:
    role = (
        await db.execute(select(Role).where(Role.code == role_code, Role.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if role is None:
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "角色不存在", http_status=400)
    return role


async def list_users(db: AsyncSession, q: UserQuery) -> PageResult:
    stmt = (
        select(AdminUser, Role)
        .join(Role, Role.id == AdminUser.role_id)
        .where(AdminUser.deleted_at.is_(None), Role.deleted_at.is_(None))
    )
    if q.keyword:
        like = f"%{q.keyword}%"
        stmt = stmt.where(or_(AdminUser.username.like(like), AdminUser.phone.like(like)))
    if q.roleCode:
        stmt = stmt.where(Role.code == q.roleCode)
    if q.status:
        stmt = stmt.where(AdminUser.status == (1 if q.status == "enabled" else 0))

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (
        await db.execute(stmt.order_by(AdminUser.id.desc()).offset(q.offset).limit(q.limit))
    ).all()
    return PageResult(
        list=[_user_item(u, r) for u, r in rows],
        total=total,
        pageNum=q.pageNum,
        pageSize=q.pageSize,
    )


async def get_user_detail(db: AsyncSession, user_id: int) -> UserDetail:
    row = (
        await db.execute(
            select(AdminUser, Role)
            .join(Role, Role.id == AdminUser.role_id)
            .where(AdminUser.id == user_id, AdminUser.deleted_at.is_(None))
        )
    ).first()
    if row is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "用户不存在", http_status=404)
    user, role = row

    # 最近操作（operation_log 前 10 条，04 §4.9）
    logs = (
        await db.execute(
            select(OperationLog)
            .where(
                OperationLog.admin_user_id == user_id,
                OperationLog.deleted_at.is_(None),
            )
            .order_by(OperationLog.created_at.desc())
            .limit(10)
        )
    ).scalars().all()
    recent = [
        UserRecentLog(
            action=OperationActionType(lg.action_type).api + ":" + lg.action_desc,
            at=to_shanghai(lg.created_at),
        )
        for lg in logs
    ]
    item = _user_item(user, role)
    return UserDetail(
        **item,
        email=user.email,
        createdAt=to_shanghai(user.created_at),
        recentLogs=recent,
    )


async def create_user(
    db: AsyncSession, ctx: AdminContext, payload: UserCreate, ip: str
) -> dict:
    if payload.roleCode == "super_admin":
        raise BizError(ErrorCode.PERM_DENIED, "不可授予超级管理员角色", http_status=403)
    role = await _require_role_by_code(db, payload.roleCode)

    exists = (
        await db.execute(
            select(AdminUser).where(
                AdminUser.username == payload.username, AdminUser.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise BizError(ErrorCode.BIZ_USERNAME_EXISTS, "用户名已存在", http_status=409)
    phone_exists = (
        await db.execute(
            select(AdminUser).where(
                AdminUser.phone == payload.phone, AdminUser.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if phone_exists is not None:
        raise BizError(ErrorCode.BIZ_PHONE_REGISTERED, "手机号已被使用", http_status=409)

    user = AdminUser(
        username=payload.username,
        password_hash=security.hash_password(payload.password),
        phone=payload.phone,
        email=payload.email,
        role_id=role.id,
        status=1 if payload.status == "enabled" else 0,
    )
    db.add(user)
    await db.flush()
    await record_operation(
        db,
        action_type=OperationActionType.CREATE,
        action_desc="新增用户",
        target=f"用户「{payload.username}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"id": user.id}


async def update_user(
    db: AsyncSession, ctx: AdminContext, user_id: int, payload: UserUpdate, ip: str
) -> dict:
    user = (
        await db.execute(
            select(AdminUser).where(AdminUser.id == user_id, AdminUser.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if user is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "用户不存在", http_status=404)

    is_builtin_super = user.username == C.ADMIN_SUPER_USERNAME
    if is_builtin_super and payload.roleCode != "super_admin":
        raise BizError(ErrorCode.BIZ_STATE_INVALID, "内置超管角色不可修改", http_status=409)
    if payload.roleCode == "super_admin" and not is_builtin_super:
        raise BizError(ErrorCode.PERM_DENIED, "不可授予超级管理员角色", http_status=403)

    # 唯一性（排除自身）
    dup = (
        await db.execute(
            select(AdminUser).where(
                AdminUser.username == payload.username,
                AdminUser.id != user_id,
                AdminUser.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if dup is not None:
        raise BizError(ErrorCode.BIZ_USERNAME_EXISTS, "用户名已存在", http_status=409)
    dup_phone = (
        await db.execute(
            select(AdminUser).where(
                AdminUser.phone == payload.phone,
                AdminUser.id != user_id,
                AdminUser.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if dup_phone is not None:
        raise BizError(ErrorCode.BIZ_PHONE_REGISTERED, "手机号已被使用", http_status=409)

    role = await _require_role_by_code(db, payload.roleCode)
    values: dict = {
        "username": payload.username,
        "phone": payload.phone,
        "email": payload.email,
        "role_id": role.id,
        "status": 1 if payload.status == "enabled" else 0,
    }
    if payload.password:
        values["password_hash"] = security.hash_password(payload.password)
    await db.execute(update(AdminUser).where(AdminUser.id == user_id).values(**values))

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="编辑用户",
        target=f"用户「{payload.username}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def delete_users(
    db: AsyncSession, ctx: AdminContext, payload: BatchIds, ip: str
) -> dict:
    rows = (
        await db.execute(
            select(AdminUser).where(
                AdminUser.id.in_(payload.ids), AdminUser.deleted_at.is_(None)
            )
        )
    ).scalars().all()
    if any(u.username == C.ADMIN_SUPER_USERNAME for u in rows):
        raise BizError(ErrorCode.BIZ_STATE_INVALID, "内置超管不可删除", http_status=409)
    if rows:
        await db.execute(
            update(AdminUser)
            .where(AdminUser.id.in_([u.id for u in rows]))
            .values(deleted_at=_dt.now(_CN_TZ).replace(tzinfo=None))
        )
        await record_operation(
            db,
            action_type=OperationActionType.DELETE,
            action_desc="删除用户" if len(rows) == 1 else f"批量删除用户（{len(rows)} 个）",
            target=f"用户「{rows[0].username}」" if len(rows) == 1 else None,
            admin_user_id=ctx.admin_id,
            admin_username=ctx.username,
            ip=ip,
        )
        await db.commit()
    return {"success": True}


async def patch_user_status(
    db: AsyncSession, ctx: AdminContext, payload: BatchIds, status: str, ip: str
) -> dict:
    rows = (
        await db.execute(
            select(AdminUser).where(
                AdminUser.id.in_(payload.ids), AdminUser.deleted_at.is_(None)
            )
        )
    ).scalars().all()
    if any(u.username == C.ADMIN_SUPER_USERNAME for u in rows):
        raise BizError(ErrorCode.BIZ_STATE_INVALID, "内置超管状态不可修改", http_status=409)
    if rows:
        await db.execute(
            update(AdminUser)
            .where(AdminUser.id.in_([u.id for u in rows]))
            .values(status=1 if status == "enabled" else 0)
        )
        await record_operation(
            db,
            action_type=OperationActionType.DISABLE,
            action_desc=("启用用户" if status == "enabled" else "禁用用户"),
            admin_user_id=ctx.admin_id,
            admin_username=ctx.username,
            ip=ip,
        )
        await db.commit()
    return {"success": True}


async def reset_user_password(
    db: AsyncSession, ctx: AdminContext, user_id: int, ip: str
) -> dict:
    user = (
        await db.execute(
            select(AdminUser).where(AdminUser.id == user_id, AdminUser.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if user is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "用户不存在", http_status=404)

    await db.execute(
        update(AdminUser)
        .where(AdminUser.id == user_id)
        .values(password_hash=security.hash_password(C.ADMIN_DEFAULT_PASSWORD))
    )
    # 该用户全部 refresh 失效（04 §4.9；改密失效口径 S5）
    r = get_redis()
    await r.set(security.user_refresh_epoch_key("admin", str(user_id)), str(_dt.now(_CN_TZ).timestamp()))

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="重置密码",
        target=f"用户「{user.username}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


# ============================================================
# 角色管理（04 §4.10，仅超管）
# ============================================================


def _role_tags(role_code: str, perm_codes: list[str]) -> list[str]:
    """permissionTags（需求 4.5.2）：全部权限/暂无权限/「组名·权限名」标签。"""
    if role_code == "super_admin":
        return ["全部权限"]
    if not perm_codes:
        return ["暂无权限"]
    return [f"{_PERM_LABELS[c][0]}·{_PERM_LABELS[c][1]}" for c in perm_codes if c in _PERM_LABELS]


async def list_roles(db: AsyncSession) -> dict:
    roles = (
        await db.execute(select(Role).where(Role.deleted_at.is_(None)).order_by(Role.id.asc()))
    ).scalars().all()
    counts = dict(
        (
            await db.execute(
                select(AdminUser.role_id, func.count())
                .where(AdminUser.deleted_at.is_(None))
                .group_by(AdminUser.role_id)
            )
        ).all()
    )
    perm_rows = (
        await db.execute(select(RolePermission.role_id, RolePermission.permission_code))
    ).all()
    perms_by_role: dict[int, list[str]] = {}
    for rid, code in perm_rows:
        perms_by_role.setdefault(rid, []).append(code)

    items = []
    for role in roles:
        codes = [] if role.code == "super_admin" else sorted(perms_by_role.get(role.id, []))
        items.append(
            RoleItem(
                id=role.id,
                code=role.code,
                name=role.name,
                description=role.description,
                isPreset=bool(role.is_preset),
                userCount=counts.get(role.id, 0),
                permissionTags=_role_tags(role.code, codes),
            )
        )
    return {"list": [i.model_dump() for i in items]}


async def create_role(db: AsyncSession, ctx: AdminContext, payload: RoleCreate, ip: str) -> dict:
    exists = (
        await db.execute(
            select(Role).where(Role.code == payload.code, Role.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise BizError(ErrorCode.BIZ_ROLE_CODE_EXISTS, "角色编码已存在", http_status=409)
    role = Role(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        is_preset=0,
    )
    db.add(role)
    await db.flush()
    await record_operation(
        db,
        action_type=OperationActionType.CREATE,
        action_desc="新增角色",
        target=f"角色「{payload.name}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"id": role.id}


async def update_role(
    db: AsyncSession, ctx: AdminContext, role_id: int, payload: RoleUpdate, ip: str
) -> dict:
    role = (
        await db.execute(select(Role).where(Role.id == role_id, Role.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if role is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "角色不存在", http_status=404)
    # S19：预置角色编码不可改（RoleUpdate 不含 code，编码天然不可变）
    await db.execute(
        update(Role)
        .where(Role.id == role_id)
        .values(name=payload.name, description=payload.description)
    )
    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="编辑角色",
        target=f"角色「{payload.name}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def update_role_permissions(
    db: AsyncSession, ctx: AdminContext, role_id: int, payload: RolePermissionsUpdate, ip: str
) -> dict:
    role = (
        await db.execute(select(Role).where(Role.id == role_id, Role.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if role is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "角色不存在", http_status=404)

    invalid = [c for c in payload.permissionCodes if c not in PERMISSION_CODES]
    if invalid:
        raise BizError(
            ErrorCode.PARAM_VALIDATION_FAILED,
            "存在非法权限码",
            http_status=400,
            data={"fieldErrors": [{"field": "permissionCodes", "reason": f"非法：{', '.join(invalid)}"}]},
        )

    # 全量覆盖：事务内物理替换（03 S2 编辑替换语义）
    await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    for code in sorted(set(payload.permissionCodes)):
        db.add(RolePermission(role_id=role_id, permission_code=code))

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="编辑角色权限",
        target=f"角色「{role.name}」",
        detail=f"授权 {len(set(payload.permissionCodes))} 个权限点",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def delete_role(db: AsyncSession, ctx: AdminContext, role_id: int, ip: str) -> dict:
    role = (
        await db.execute(select(Role).where(Role.id == role_id, Role.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if role is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "角色不存在", http_status=404)
    if role.is_preset:
        raise BizError(ErrorCode.BIZ_STATE_INVALID, "预置角色不可删除", http_status=409)
    user_count = (
        await db.execute(
            select(func.count())
            .select_from(AdminUser)
            .where(AdminUser.role_id == role_id, AdminUser.deleted_at.is_(None))
        )
    ).scalar_one()
    if user_count > 0:
        raise BizError(ErrorCode.BIZ_ROLE_IN_USE, "角色下有用户，不可删除", http_status=409)

    await db.execute(update(Role).where(Role.id == role_id).values(deleted_at=_dt.now(_CN_TZ).replace(tzinfo=None)))
    await record_operation(
        db,
        action_type=OperationActionType.DELETE,
        action_desc="删除角色",
        target=f"角色「{role.name}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


# ============================================================
# 操作日志（04 §4.11）
# ============================================================


def _log_item(lg: OperationLog) -> dict:
    return {
        "id": lg.id,
        "adminUsername": lg.admin_username,
        "actionType": OperationActionType(lg.action_type).api,
        "actionDesc": lg.action_desc,
        "target": lg.target,
        "detail": lg.detail,
        "ip": lg.ip,
        "createdAt": to_shanghai(lg.created_at),
    }


def _log_filtered(q: LogQuery):
    stmt = select(OperationLog).where(OperationLog.deleted_at.is_(None))
    if q.keyword:
        like = f"%{q.keyword}%"
        stmt = stmt.where(
            or_(
                OperationLog.admin_username.like(like),
                OperationLog.action_desc.like(like),
                OperationLog.target.like(like),
            )
        )
    if q.actionType and q.actionType != "all":
        stmt = stmt.where(OperationLog.action_type == int(OperationActionType.from_api(q.actionType)))
    if q.dateFrom:
        # 日界按 Asia/Shanghai（D9），入库 UTC
        start = _dt.combine(_dt.strptime(q.dateFrom, "%Y-%m-%d").date(), _time.min, tzinfo=_CN_TZ)
        stmt = stmt.where(OperationLog.created_at >= start.astimezone(timezone.utc).replace(tzinfo=None))
    if q.dateTo:
        end = _dt.combine(_dt.strptime(q.dateTo, "%Y-%m-%d").date(), _time.max, tzinfo=_CN_TZ)
        stmt = stmt.where(OperationLog.created_at <= end.astimezone(timezone.utc).replace(tzinfo=None))
    if q.adminUserId:
        stmt = stmt.where(OperationLog.admin_user_id == q.adminUserId)
    return stmt


async def list_logs(db: AsyncSession, q: LogQuery) -> PageResult:
    stmt = _log_filtered(q)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(stmt.order_by(OperationLog.created_at.desc()).offset(q.offset).limit(q.limit))
    ).scalars().all()
    return PageResult(
        list=[_log_item(lg) for lg in rows], total=total, pageNum=q.pageNum, pageSize=q.pageSize
    )


async def get_log(db: AsyncSession, log_id: int) -> LogDetail:
    lg = (
        await db.execute(
            select(OperationLog).where(OperationLog.id == log_id, OperationLog.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if lg is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "日志不存在", http_status=404)
    return LogDetail(**_log_item(lg), adminUserId=lg.admin_user_id)


async def export_logs_csv(
    db: AsyncSession, ctx: AdminContext, q: LogQuery, ip: str
) -> tuple[str, bytes]:
    """导出 CSV（UTF-8 BOM，04 §4.11）；导出行为本身入日志（B5）。"""
    import csv
    import io as _io

    stmt = _log_filtered(q).order_by(OperationLog.created_at.desc()).limit(C.EXPORT_MAX_ROWS)
    rows = (await db.execute(stmt)).scalars().all()

    buf = _io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["日志ID", "操作人", "操作类型", "操作", "目标", "详情", "IP地址", "时间"])
    for lg in rows:
        item = _log_item(lg)
        writer.writerow(
            [item["id"], item["adminUsername"] or "", item["actionType"], item["actionDesc"],
             item["target"] or "", item["detail"] or "", item["ip"], item["createdAt"]]
        )

    # 导出行为入日志（B5 ✅ 归并 other）
    await record_operation(
        db,
        action_type=OperationActionType.OTHER,
        action_desc="导出操作日志",
        detail=f"导出 {len(rows)} 条",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return "operation-logs.csv", buf.getvalue().encode("utf-8-sig")


async def clear_logs(db: AsyncSession, ctx: AdminContext, ip: str) -> dict:
    """清空日志 = 批量逻辑删除（03 S3）。"""
    n = (
        await db.execute(
            select(func.count()).select_from(OperationLog).where(OperationLog.deleted_at.is_(None))
        )
    ).scalar_one()
    await db.execute(
        update(OperationLog)
        .where(OperationLog.deleted_at.is_(None))
        .values(deleted_at=_dt.now(_CN_TZ).replace(tzinfo=None))
    )
    await record_operation(
        db,
        action_type=OperationActionType.DELETE,
        action_desc="清空日志",
        detail=f"共 {n} 条",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


# ============================================================
# 系统设置（04 §4.12）
# ============================================================


async def _get_setting_row(db: AsyncSession) -> SystemSetting:
    row = (await db.execute(select(SystemSetting).where(SystemSetting.id == 1))).scalar_one_or_none()
    if row is None:
        row = SystemSetting(id=1)  # 平台名称/好评率走模型默认值
        db.add(row)
        await db.flush()
    return row


async def get_system_settings(db: AsyncSession) -> SettingsResult:
    row = await _get_setting_row(db)
    return SettingsResult(
        platformName=row.platform_name,
        platformDescription=row.platform_description,
        logoUrl=row.logo_url,
        defaultAvatarUrl=row.default_avatar_url,
    )


async def get_public_settings(db: AsyncSession) -> dict:
    """平台公开配置（04 §3.2 GET /settings/public，游客，两端共用）。

    只读不建行；仅公开四项，goodRate 为首页内部值不对外（口径 S20）。
    """
    row = (
        await db.execute(select(SystemSetting).where(SystemSetting.id == 1))
    ).scalar_one_or_none()
    return {
        "platformName": row.platform_name if row else "云枢智学",
        "platformDescription": row.platform_description if row else None,
        "logoUrl": row.logo_url if row else None,
        "defaultAvatarUrl": row.default_avatar_url if row else None,
    }


async def save_system_settings(
    db: AsyncSession, ctx: AdminContext, payload: SettingsUpdate, ip: str
) -> dict:
    row = await _get_setting_row(db)
    await db.execute(
        update(SystemSetting)
        .where(SystemSetting.id == row.id)
        .values(
            platform_name=payload.platformName,
            platform_description=payload.platformDescription,
            logo_url=payload.logoUrl,
            default_avatar_url=payload.defaultAvatarUrl,
        )
    )
    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="修改系统设置",
        target=f"平台名称「{payload.platformName}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}
