"""公共工具：时间口径（04 §1.1 / 02 D9）。

约定：
  - DB 时间列 naive UTC；API 请求/响应时间统一 Asia/Shanghai 本地字符串
    `YYYY-MM-DD HH:mm:ss`（毫秒场景 `YYYY-MM-DD HH:mm:ss.SSS`）；
  - 日界类口径（连续学习天数/每日配额 0 点重置）按 Asia/Shanghai 计算。
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings

CN_TZ = ZoneInfo("Asia/Shanghai")

FMT_DATETIME = "%Y-%m-%d %H:%M:%S"


def utc_now() -> datetime:
    """当前 UTC 时间（naive，与 DB DATETIME 列对齐）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def now_ts() -> float:
    """真实 Unix 秒（与 JWT iat 同量纲；naive .timestamp() 会被误当本地时间偏移时区）。"""
    return datetime.now(timezone.utc).timestamp()


def to_shanghai(dt: datetime | None) -> str | None:
    """UTC 时间 → Asia/Shanghai 展示字符串。"""
    if dt is None:
        return None
    aware = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    return aware.astimezone(CN_TZ).strftime(FMT_DATETIME)


def shanghai_today() -> datetime:
    """Asia/Shanghai 今日 0 点对应的 UTC 时间（每日配额/学习天数日界口径）。"""
    now_cn = datetime.now(timezone.utc).astimezone(CN_TZ)
    midnight_cn = now_cn.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight_cn.astimezone(timezone.utc).replace(tzinfo=None)


def app_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().app_timezone)
