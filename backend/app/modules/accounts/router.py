"""accounts 路由（挂载于 /api/portal/v1）。接口清单见 04 §2.1 #1-#10（§3.1）。

  POST /auth/sms-code | /auth/register | /auth/login/password | /auth/login/sms
  POST /auth/password/reset | /auth/refresh | /auth/logout
  GET/PUT /profile | POST /profile/avatar
找回密码页本期为占位（接口已就绪）；学员/后台账号双身份见 service 注释（Q4）。
"""
from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.core.database import get_db
from app.core.deps import StudentContext, get_current_student
from app.core.redis import get_redis
from app.core.response import ok
from app.modules.accounts import service
from app.modules.accounts.schemas import (
    LoginPasswordRequest,
    LoginSmsRequest,
    LogoutRequest,
    PasswordResetRequest,
    ProfileUpdate,
    RefreshRequest,
    RegisterRequest,
    SmsCodeRequest,
)

router = APIRouter(tags=["accounts"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


# ===================== 验证码 / 注册（游客） =====================


@router.post("/auth/sms-code")
async def send_sms_code(
    payload: SmsCodeRequest,
    request: Request,
    r: aioredis.Redis = Depends(get_redis),
):
    """获取手机验证码（开发阶段 Mock 回传 mockCode 页面弹窗展示；真实供应商不回传本体）。"""
    return ok(await service.send_sms_code(r, payload, ip=_client_ip(request)))


@router.post("/auth/register")
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """注册（成功即登录 ⚠️ 口径 S3）。"""
    return ok(await service.register(db, r, payload, ip=_client_ip(request)), status_code=201)


# ===================== 登录 / 找回 / 刷新 / 退出 =====================


@router.post("/auth/login/password")
async def login_by_password(
    payload: LoginPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """账号密码登录（学员优先、兼容后台账号 Q4；5 次错锁 5 分钟）。"""
    return ok(await service.login_password(db, r, payload, ip=_client_ip(request)))


@router.post("/auth/login/sms")
async def login_by_sms(
    payload: LoginSmsRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """手机验证码登录（仅已注册学员，S10）。"""
    return ok(await service.login_sms(db, r, payload, ip=_client_ip(request)))


@router.post("/auth/password/reset")
async def reset_password(
    payload: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """找回密码（重置后该学员全部 refresh 失效，S5）。"""
    return ok(await service.reset_password(db, r, payload, ip=_client_ip(request)))


@router.post("/auth/refresh")
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """刷新 access token（refresh 滚动续期；双端密钥按 clientType 区分）。"""
    return ok(await service.refresh_tokens(db, r, payload))


@router.post("/auth/logout")
async def logout(
    payload: LogoutRequest,
    ctx: StudentContext = Depends(get_current_student),
    r: aioredis.Redis = Depends(get_redis),
):
    """退出登录（refresh 立即失效，04 §1.5）。"""
    return ok(await service.logout(r, ctx, payload))


# ===================== 个人中心（04 §3.1） =====================


@router.get("/profile")
async def get_profile(
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """个人基本信息（手机号完整返回、前端脱敏展示 S6）。"""
    return ok(await service.get_profile(db, ctx))


@router.put("/profile")
async def update_profile(
    payload: ProfileUpdate,
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """修改基本信息（手机号只读；admin 身份仅昵称/头像 S4）。"""
    return ok(await service.update_profile(db, ctx, payload))


@router.post("/profile/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    ctx: StudentContext = Depends(get_current_student),
):
    """上传头像（jpg/png ≤2MB → MinIO）→ { url }。"""
    data = await file.read()
    return ok(await service.upload_avatar(ctx, data, file.content_type or ""))
