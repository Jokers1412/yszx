"""Redis 连接（redis.asyncio）。

职责（02 §1.3.3 / D12）：验证码存储与频控、登录失败锁定、AI 面试每日配额、
接口限流、refresh 失效标记、导入 importToken——全部带 TTL 的计数/KV 场景。
"""
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import get_settings

_client: Optional[aioredis.Redis] = None


def get_redis() -> aioredis.Redis:
    """获取全局 Redis 客户端（FastAPI 依赖 / 服务层共用）。"""
    global _client
    if _client is None:
        _client = aioredis.from_url(
            get_settings().redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
