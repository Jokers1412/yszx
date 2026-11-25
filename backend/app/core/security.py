"""JWT 签发校验 + 密码哈希（04 §1.5、02 D3）。

双端隔离：学员端（aud=portal）与管理端（aud=admin）两套独立 JWT（不同密钥/受众），
互不通用；access 2 小时，refresh 7/30 天（记住我），refresh 失效由 Redis 标记（D12）。
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import hashlib
import jwt

from app.core.config import get_settings

Audience = Literal["portal", "admin"]
TokenType = Literal["access", "refresh"]

_ALGORITHM = "HS256"


# ---------- 密码 ----------

def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------- JWT ----------

def _secret(audience: Audience) -> str:
    settings = get_settings()
    return settings.jwt_secret_portal if audience == "portal" else settings.jwt_secret_admin


def create_access_token(subject: str, audience: Audience, extra: dict[str, Any] | None = None) -> str:
    """签发 access token（sub=用户 id）。"""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "aud": audience,
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_ttl_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _secret(audience), algorithm=_ALGORITHM)


def create_refresh_token(
    subject: str, audience: Audience, remember: bool = False
) -> tuple[str, int]:
    """签发 refresh token，返回 (token, 有效期秒数)。"""
    settings = get_settings()
    ttl_days = settings.jwt_refresh_ttl_days_remember if remember else settings.jwt_refresh_ttl_days
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=ttl_days)
    payload = {
        "sub": subject,
        "aud": audience,
        "typ": "refresh",
        "rem": bool(remember),  # 记住我标记：refresh 滚动续期时沿用原有效期档位
        "iat": now,
        "exp": exp,
    }
    token = jwt.encode(payload, _secret(audience), algorithm=_ALGORITHM)
    return token, int((exp - now).total_seconds())


def decode_token(
    token: str,
    audience: Audience,
    token_type: TokenType = "access",
) -> dict[str, Any]:
    """校验并解码 JWT；失败抛 jwt.PyJWTError（由调用方转 AUTH_* 业务码）。"""
    payload = jwt.decode(
        token,
        _secret(audience),
        algorithms=[_ALGORITHM],
        audience=audience,
        options={"require": ["exp", "sub", "typ"]},
    )
    if payload.get("typ") != token_type:
        raise jwt.InvalidTokenError("token type mismatch")
    return payload


# ---------- refresh 失效（04 §1.5：登出/改密/重置 → refresh 失效）----------

# 学员端兼容后台账号登录（04 §1.5 Q4）：portal token 的 sub 对后台身份加前缀，
# 与学员 id 天然隔离（epoch 失效键等按 subject 字符串命名空间化）
ADMIN_SUBJECT_PREFIX = "adm:"


def admin_portal_subject(admin_id: int) -> str:
    """portal 端后台账号身份的 token sub（如 adm:3）。"""
    return f"{ADMIN_SUBJECT_PREFIX}{admin_id}"


def parse_portal_subject(subject: str) -> tuple[int, bool]:
    """解析 portal token sub → (id, is_admin)。"""
    if subject.startswith(ADMIN_SUBJECT_PREFIX):
        return int(subject[len(ADMIN_SUBJECT_PREFIX):]), True
    return int(subject), False


def _token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_revoke_key(audience: Audience, token: str) -> str:
    return f"yszx:auth:revoked:{audience}:{_token_fingerprint(token)}"


def user_refresh_epoch_key(audience: Audience, subject: str) -> str:
    """按用户记录 refresh 失效时间戳（改密/重置密码整端失效）。"""
    return f"yszx:auth:epoch:{audience}:{subject}"
