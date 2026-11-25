"""accounts 业务服务（04 §3.1 账号与个人中心）。

口径：
  - 注册即登录（S3）；注册默认昵称「学员+手机尾号」，可后改；
  - 密码登录学员优先、未命中查后台账号（Q4，isAdmin 标识仅用于显示管理后台入口）；
  - 锁定/验证码频控经 core.ratelimit（04 §1.7 T6 阈值）；短信经 core.sms（Mock）；
  - 登出/改密/重置 → refresh 失效（04 §1.5：单 token 作废 + epoch 整端失效）；
  - 资料维护：手机号只读（S6 前端脱敏展示）；admin 身份仅改昵称/头像（S4，
    昵称映射 admin_user.username——该表无 nickname 列，同管理端 _brief 派生口径）。
"""
import secrets

import jwt as pyjwt
import redis.asyncio as aioredis
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common import constants as C
from app.common.enums import Gender
from app.common.error_codes import ErrorCode
from app.common.utils import now_ts, to_shanghai, utc_now
from app.core import security, sms, storage
from app.core.config import get_settings
from app.core.deps import StudentContext
from app.core.exceptions import BizError
from app.core.ratelimit import (
    check_ip_account_limit,
    check_login_locked,
    check_rate_limit,
    check_sms_send_allowed,
    clear_login_fail,
    record_login_fail,
    record_sms_verify_fail,
)
from app.modules.accounts.models import Student
from app.modules.accounts.schemas import (
    AuthResult,
    AuthUserBrief,
    LoginPasswordRequest,
    LoginSmsRequest,
    LogoutRequest,
    PasswordResetRequest,
    ProfileResult,
    ProfileUpdate,
    RefreshRequest,
    RegisterRequest,
    SmsCodeRequest,
)
from app.modules.system.models import AdminUser


def _lock_key(account: str) -> str:
    return f"portal:{account.strip().lower()}"


def _sms_code_id(scene: str, phone: str) -> str:
    return f"{scene}:{phone}"


def _sms_code_key(code_id: str) -> str:
    # 与 core.ratelimit.record_sms_verify_fail 的删除键保持一致
    return f"yszx:rl:sms:code:{code_id}"


def _epoch_key(audience: str, subject: str) -> str:
    return security.user_refresh_epoch_key(audience, subject)  # type: ignore[arg-type]


def _issue_tokens(subject: str, remember: bool) -> tuple[str, str, int]:
    settings = get_settings()
    access = security.create_access_token(subject, "portal")
    refresh, _ttl = security.create_refresh_token(subject, "portal", remember=remember)
    return access, refresh, settings.jwt_access_ttl_minutes * 60


async def _verify_sms_code(r: aioredis.Redis, scene: str, phone: str, code: str) -> None:
    code_id = _sms_code_id(scene, phone)
    stored = await r.get(_sms_code_key(code_id))
    if stored is None:
        raise BizError(ErrorCode.AUTH_SMS_CODE_EXPIRED, "验证码已过期，请重新获取", http_status=400)
    if stored != code:
        # 连续 5 次校验失败即失效（04 §1.7；达阈值由 record_sms_verify_fail 抛出）
        await record_sms_verify_fail(r, code_id)
        raise BizError(ErrorCode.AUTH_SMS_CODE_INVALID, "验证码错误", http_status=400)
    await r.delete(_sms_code_key(code_id))


# ============================================================
# 验证码 / 注册
# ============================================================


async def send_sms_code(r: aioredis.Redis, payload: SmsCodeRequest, ip: str) -> dict:
    """获取短信验证码（60s 1 次、日 10 次；scene=login 对未注册手机号统一成功，S10）。"""
    settings = get_settings()
    await check_ip_account_limit(
        r, "portal_sms", ip, payload.phone, settings.rate_limit_sms_code_per_hour
    )
    await check_sms_send_allowed(r, payload.phone)

    code = f"{secrets.randbelow(10 ** C.SMS_CODE_LENGTH):0{C.SMS_CODE_LENGTH}d}"
    await r.set(_sms_code_key(_sms_code_id(payload.scene, payload.phone)), code, ex=C.SMS_CODE_TTL_SECONDS)
    await sms.send_sms_code(payload.phone, code)

    return {"sentAt": to_shanghai(utc_now())}


async def register(db: AsyncSession, r: aioredis.Redis, payload: RegisterRequest, ip: str) -> dict:
    """注册（成功即登录 ⚠️ 口径 S3）。"""
    settings = get_settings()
    await check_rate_limit(
        r, f"yszx:rl:ip:portal_register:{ip}", settings.rate_limit_register_per_hour, 3600
    )
    await check_rate_limit(
        r, f"yszx:rl:acct:portal_register:{payload.phone}",
        settings.rate_limit_register_per_hour, 3600,
    )
    await _verify_sms_code(r, "register", payload.phone, payload.code)

    exists = (
        await db.execute(
            select(Student.id).where(Student.phone == payload.phone, Student.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise BizError(ErrorCode.BIZ_PHONE_REGISTERED, "该手机号已注册", http_status=409)

    student = Student(
        phone=payload.phone,
        password_hash=security.hash_password(payload.password),
        nickname=f"学员{payload.phone[-4:]}",  # 默认昵称，注册后可在个人中心修改
        gender=int(Gender.SECRET),
        last_login_at=utc_now(),  # 注册即登录
    )
    db.add(student)
    await db.flush()

    access, refresh, expires_in = _issue_tokens(str(student.id), remember=True)
    await db.commit()
    return AuthResult(
        accessToken=access,
        refreshToken=refresh,
        expiresIn=expires_in,
        user=AuthUserBrief(
            id=student.id, nickname=student.nickname, avatarUrl=None, isAdmin=False
        ),
    ).model_dump()


# ============================================================
# 登录
# ============================================================


async def login_password(
    db: AsyncSession, r: aioredis.Redis, payload: LoginPasswordRequest, ip: str
) -> dict:
    """账号密码登录：学员优先，未命中查后台账号（Q4）。连续 5 次错误锁 5 分钟。"""
    settings = get_settings()
    await check_ip_account_limit(
        r, "portal_login", ip, payload.account, settings.rate_limit_login_per_minute
    )
    await check_login_locked(r, _lock_key(payload.account))

    account = payload.account.strip()
    student = (
        await db.execute(
            select(Student).where(
                or_(Student.phone == account, Student.email == account),
                Student.deleted_at.is_(None),
            )
        )
    ).scalars().first()

    if student is not None:
        if not security.verify_password(payload.password, student.password_hash):
            await record_login_fail(r, _lock_key(payload.account))
            raise BizError(ErrorCode.AUTH_INVALID_CREDENTIALS, "账号或密码错误", http_status=401)
        if student.status != 1:
            raise BizError(ErrorCode.AUTH_ACCOUNT_DISABLED, "账号已被禁用", http_status=403)

        await clear_login_fail(r, _lock_key(payload.account))
        await db.execute(
            update(Student).where(Student.id == student.id).values(last_login_at=utc_now())
        )
        access, refresh, expires_in = _issue_tokens(
            str(student.id), remember=payload.rememberMe
        )
        await db.commit()
        return AuthResult(
            accessToken=access,
            refreshToken=refresh,
            expiresIn=expires_in,
            user=AuthUserBrief(
                id=student.id,
                nickname=student.nickname,
                avatarUrl=student.avatar_url,
                isAdmin=False,
            ),
        ).model_dump()

    # 后台账号（Q4）：账号名/手机号/邮箱均可命中
    admin = (
        await db.execute(
            select(AdminUser).where(
                or_(
                    AdminUser.username == account,
                    AdminUser.phone == account,
                    AdminUser.email == account,
                ),
                AdminUser.deleted_at.is_(None),
            )
        )
    ).scalars().first()
    if admin is not None and security.verify_password(payload.password, admin.password_hash):
        if admin.status != 1:
            raise BizError(ErrorCode.AUTH_ACCOUNT_DISABLED, "账号已被禁用", http_status=403)
        await clear_login_fail(r, _lock_key(payload.account))
        await db.execute(
            update(AdminUser).where(AdminUser.id == admin.id).values(last_login_at=utc_now())
        )
        access, refresh, expires_in = _issue_tokens(
            security.admin_portal_subject(admin.id), remember=payload.rememberMe
        )
        await db.commit()
        return AuthResult(
            accessToken=access,
            refreshToken=refresh,
            expiresIn=expires_in,
            user=AuthUserBrief(
                id=admin.id,
                nickname=admin.username,  # admin_user 无 nickname 列（_brief 同口径）
                avatarUrl=admin.avatar_url,
                isAdmin=True,
            ),
        ).model_dump()

    if admin is not None:
        await record_login_fail(r, _lock_key(payload.account))
    raise BizError(ErrorCode.AUTH_INVALID_CREDENTIALS, "账号或密码错误", http_status=401)


async def login_sms(
    db: AsyncSession, r: aioredis.Redis, payload: LoginSmsRequest, ip: str
) -> dict:
    """手机验证码登录：仅已注册学员（后台账号不走验证码登录，S10）。"""
    settings = get_settings()
    await check_ip_account_limit(
        r, "portal_login", ip, payload.phone, settings.rate_limit_login_per_minute
    )
    await _verify_sms_code(r, "login", payload.phone, payload.code)

    student = (
        await db.execute(
            select(Student).where(Student.phone == payload.phone, Student.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if student is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "该手机号尚未注册", http_status=404)
    if student.status != 1:
        raise BizError(ErrorCode.AUTH_ACCOUNT_DISABLED, "账号已被禁用", http_status=403)

    await db.execute(
        update(Student).where(Student.id == student.id).values(last_login_at=utc_now())
    )
    access, refresh, expires_in = _issue_tokens(str(student.id), remember=payload.rememberMe)
    await db.commit()
    return AuthResult(
        accessToken=access,
        refreshToken=refresh,
        expiresIn=expires_in,
        user=AuthUserBrief(
            id=student.id,
            nickname=student.nickname,
            avatarUrl=student.avatar_url,
            isAdmin=False,
        ),
    ).model_dump()


# ============================================================
# 找回密码 / token 刷新 / 退出
# ============================================================


async def reset_password(
    db: AsyncSession, r: aioredis.Redis, payload: PasswordResetRequest, ip: str
) -> dict:
    """找回密码：重置后该学员全部 refresh 失效（口径 S5）。"""
    settings = get_settings()
    await check_rate_limit(
        r, f"yszx:rl:ip:portal_reset:{ip}", settings.rate_limit_register_per_hour, 3600
    )
    await _verify_sms_code(r, "reset", payload.phone, payload.code)

    student = (
        await db.execute(
            select(Student).where(Student.phone == payload.phone, Student.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if student is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "该手机号尚未注册", http_status=404)

    await db.execute(
        update(Student)
        .where(Student.id == student.id)
        .values(password_hash=security.hash_password(payload.newPassword))
    )
    await r.set(_epoch_key("portal", str(student.id)), str(now_ts()))
    await db.commit()
    return {"success": True}


async def refresh_tokens(db: AsyncSession, r: aioredis.Redis, payload: RefreshRequest) -> dict:
    """刷新 access（refresh 滚动续期，04 §1.5）；失效链路 → AUTH_REFRESH_INVALID。"""
    audience = payload.clientType
    try:
        claims = security.decode_token(payload.refreshToken, audience, "refresh")  # type: ignore[arg-type]
    except pyjwt.PyJWTError:
        raise BizError(ErrorCode.AUTH_REFRESH_INVALID, "登录态已失效，请重新登录", http_status=401)

    revoked = await r.exists(security.refresh_revoke_key(audience, payload.refreshToken))  # type: ignore[arg-type]
    if revoked:
        raise BizError(ErrorCode.AUTH_REFRESH_INVALID, "登录态已失效，请重新登录", http_status=401)

    subject = str(claims["sub"])
    epoch = await r.get(_epoch_key(audience, subject))
    if epoch is not None and float(claims.get("iat", 0)) < float(epoch):
        raise BizError(ErrorCode.AUTH_REFRESH_INVALID, "登录态已失效，请重新登录", http_status=401)

    # 主体仍需有效（学员删除/禁用、后台账号停用均不可续期）
    if audience == "portal":
        user_id, is_admin = security.parse_portal_subject(subject)
        model = AdminUser if is_admin else Student
    else:
        user_id, model = int(subject), AdminUser
    row = (
        await db.execute(select(model).where(model.id == user_id, model.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if row is None or row.status != 1:
        raise BizError(ErrorCode.AUTH_REFRESH_INVALID, "登录态已失效，请重新登录", http_status=401)

    access = security.create_access_token(subject, audience)  # type: ignore[arg-type]
    new_refresh, _ttl = security.create_refresh_token(
        subject, audience, remember=bool(claims.get("rem", False))  # type: ignore[arg-type]
    )
    return {
        "accessToken": access,
        "expiresIn": get_settings().jwt_access_ttl_minutes * 60,
        "refreshToken": new_refresh,  # 滚动续期
    }


async def logout(
    r: aioredis.Redis, ctx: StudentContext, payload: LogoutRequest
) -> dict:
    """退出登录：该 refresh 立即作废 + epoch 整端失效（04 §1.5 失效链路）。"""
    if payload.refreshToken:
        max_ttl = get_settings().jwt_refresh_ttl_days_remember * 24 * 3600
        await r.set(
            security.refresh_revoke_key("portal", payload.refreshToken), "1", ex=max_ttl
        )
    await r.set(_epoch_key("portal", ctx.subject), str(now_ts()))
    return {"success": True}


# ============================================================
# 个人中心（04 §3.1）
# ============================================================


async def get_profile(db: AsyncSession, ctx: StudentContext) -> dict:
    """个人基本信息（手机号完整返回、前端脱敏展示，口径 S6）。"""
    if ctx.is_admin:
        admin = (
            await db.execute(
                select(AdminUser).where(AdminUser.id == ctx.admin_id, AdminUser.deleted_at.is_(None))
            )
        ).scalar_one()
        return ProfileResult(
            id=admin.id,
            nickname=admin.username,
            phone=admin.phone,
            email=admin.email,
            gender=None,
            avatarUrl=admin.avatar_url,
            isAdmin=True,
            createdAt=to_shanghai(admin.created_at),
            lastLoginAt=to_shanghai(admin.last_login_at),
        ).model_dump()

    student = (
        await db.execute(
            select(Student).where(Student.id == ctx.student_id, Student.deleted_at.is_(None))
        )
    ).scalar_one()
    return _student_profile(student).model_dump()


def _student_profile(student: Student) -> ProfileResult:
    return ProfileResult(
        id=student.id,
        nickname=student.nickname,
        phone=student.phone,
        email=student.email,
        gender=Gender(student.gender).api,
        avatarUrl=student.avatar_url,
        isAdmin=False,
        createdAt=to_shanghai(student.created_at),
        lastLoginAt=to_shanghai(student.last_login_at),
    )


async def update_profile(
    db: AsyncSession, ctx: StudentContext, payload: ProfileUpdate
) -> dict:
    """修改基本信息（请求/响应均不含手机号变更，S6 只读）。

    admin 身份仅允许改昵称/头像（S4）：昵称映射 admin_user.username（唯一校验），
    试图改邮箱/性别 → 400。
    """
    if ctx.is_admin:
        admin = (
            await db.execute(
                select(AdminUser).where(AdminUser.id == ctx.admin_id, AdminUser.deleted_at.is_(None))
            )
        ).scalar_one()
        if (payload.email or "") != (admin.email or "") or payload.gender != Gender.SECRET.api:
            raise BizError(
                ErrorCode.PARAM_VALIDATION_FAILED,
                "后台账号仅支持修改昵称与头像",
                http_status=400,
            )
        if payload.nickname != admin.username:
            dup = (
                await db.execute(
                    select(AdminUser.id).where(
                        AdminUser.username == payload.nickname,
                        AdminUser.deleted_at.is_(None),
                        AdminUser.id != admin.id,
                    )
                )
            ).scalar_one_or_none()
            if dup is not None:
                raise BizError(ErrorCode.BIZ_USERNAME_EXISTS, "该用户名已存在", http_status=409)
            await db.execute(
                update(AdminUser)
                .where(AdminUser.id == admin.id)
                .values(username=payload.nickname, avatar_url=payload.avatarUrl)
            )
        else:
            await db.execute(
                update(AdminUser)
                .where(AdminUser.id == admin.id)
                .values(avatar_url=payload.avatarUrl)
            )
        await db.commit()
        return await get_profile(db, ctx)

    await db.execute(
        update(Student)
        .where(Student.id == ctx.student_id, Student.deleted_at.is_(None))
        .values(
            nickname=payload.nickname,
            email=payload.email,
            gender=int(Gender.from_api(payload.gender)),
            avatar_url=payload.avatarUrl,
        )
    )
    await db.commit()
    return await get_profile(db, ctx)


async def upload_avatar(ctx: StudentContext, data: bytes, content_type: str) -> dict:
    """上传头像（jpg/png ≤2MB → MinIO，02 D15）→ { url }。"""
    url = storage.upload_image(data, content_type, subdir="avatars")
    return {"url": url}
