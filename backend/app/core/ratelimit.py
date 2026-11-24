"""安全与频控（04 §1.7 / 02 D12，T6 定稿阈值；服务端 Redis 实现）。

覆盖：
  - 登录失败锁定：连续 5 次密码错误锁 5 分钟（423 AUTH_LOCKED，提示剩余分钟）；
  - 验证码获取：同手机号 60s 1 次、日 10 次；
  - 验证码校验失败：同验证码连续 5 次失效；
  - 接口限流：IP + 账号双维度（429 RATE_LIMITED，不暴露具体阈值）。

阈值常量见 app.common.constants；频控键前缀 yszx:rl:*。
"""
from datetime import date

import redis.asyncio as aioredis

from app.common import constants as C
from app.common.error_codes import ErrorCode
from app.core.exceptions import BizError

_PREFIX = "yszx:rl"


# ---------- 通用计数 ----------

async def incr_window(r: aioredis.Redis, key: str, window_seconds: int) -> int:
    """窗口内计数 +1（带 TTL），返回当前计数。"""
    n = await r.incr(key)
    if n == 1:
        await r.expire(key, window_seconds)
    return n


async def check_rate_limit(
    r: aioredis.Redis, key: str, limit: int, window_seconds: int
) -> None:
    """通用限流：窗口内超过 limit → 429 RATE_LIMITED。"""
    n = await incr_window(r, key, window_seconds)
    if n > limit:
        raise BizError(ErrorCode.RATE_LIMITED, "操作过于频繁，请稍后再试", http_status=429)


async def check_ip_account_limit(
    r: aioredis.Redis, scene: str, ip: str, account: str | None, limit: int
) -> None:
    """IP + 账号双维度限流（04 §1.7）。"""
    await check_rate_limit(r, f"{_PREFIX}:ip:{scene}:{ip}", limit, 60)
    if account:
        await check_rate_limit(r, f"{_PREFIX}:acct:{scene}:{account}", limit, 60)


# ---------- 登录失败锁定 ----------

async def check_login_locked(r: aioredis.Redis, account_key: str) -> None:
    """锁定中 → 423 AUTH_LOCKED（提示剩余分钟，不暴露阈值）。"""
    ttl = await r.ttl(f"{_PREFIX}:lock:{account_key}")
    if ttl and ttl > 0:
        minutes = max(1, (ttl + 59) // 60)
        raise BizError(
            ErrorCode.AUTH_LOCKED,
            f"账号已锁定，请 {minutes} 分钟后重试",
            http_status=423,
            data={"remainingMinutes": minutes},
        )


async def record_login_fail(r: aioredis.Redis, account_key: str) -> None:
    """记录 1 次密码错误；达阈值锁定并清零计数。"""
    key = f"{_PREFIX}:loginfail:{account_key}"
    n = await r.incr(key)
    if n == 1:
        await r.expire(key, C.LOGIN_LOCK_SECONDS)
    if n >= C.LOGIN_FAIL_MAX:
        await r.set(f"{_PREFIX}:lock:{account_key}", "1", ex=C.LOGIN_LOCK_SECONDS)
        await r.delete(key)


async def clear_login_fail(r: aioredis.Redis, account_key: str) -> None:
    """登录成功清零失败计数。"""
    await r.delete(f"{_PREFIX}:loginfail:{account_key}")


# ---------- 验证码频控 ----------

async def check_sms_send_allowed(r: aioredis.Redis, phone: str) -> None:
    """同手机号 60s 1 次、每日 10 次。"""
    interval_key = f"{_PREFIX}:sms:interval:{phone}"
    if await r.exists(interval_key):
        raise BizError(ErrorCode.RATE_LIMITED, "获取过于频繁，请稍后再试", http_status=429)
    daily_key = f"{_PREFIX}:sms:daily:{phone}:{date.today().isoformat()}"
    n = await r.incr(daily_key)
    if n == 1:
        # 到次日 0 点（Asia/Shanghai）过期；86400+ 缓冲由应用日界口径兜底
        await r.expire(daily_key, 26 * 3600)
    if n > C.SMS_DAILY_LIMIT:
        raise BizError(ErrorCode.RATE_LIMITED, "今日获取次数已达上限", http_status=429)
    await r.set(interval_key, "1", ex=C.SMS_SEND_INTERVAL_SECONDS)


async def record_sms_verify_fail(r: aioredis.Redis, code_id: str) -> None:
    """同验证码连续校验失败 5 次即失效。"""
    key = f"{_PREFIX}:sms:fail:{code_id}"
    n = await incr_window(r, key, C.SMS_CODE_TTL_SECONDS)
    if n >= C.SMS_VERIFY_FAIL_MAX:
        await r.delete(f"{_PREFIX}:sms:code:{code_id}")
        raise BizError(
            ErrorCode.AUTH_SMS_CODE_LOCKED, "验证码已失效，请重新获取", http_status=429
        )
