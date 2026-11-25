"""应用配置（pydantic-settings，读取环境变量 / .env）。

约定（02 §2.2 / D9）：
  - DB 连接时区 UTC（存储 UTC，展示层转 Asia/Shanghai）；
  - 双端 JWT 独立密钥与受众（02 D3）；
  - AI / 短信供应商可配置，联调期 Mock（02 D5/D17）。
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- 应用 ----
    app_name: str = "云枢智学"
    debug: bool = False
    app_timezone: str = "Asia/Shanghai"  # 展示/日界口径（D9）

    # ---- 数据层 ----
    database_url: str = (
        "mysql+aiomysql://root:yszx_root_2026@127.0.0.1:3307/yszx?charset=utf8mb4"
    )
    redis_url: str = "redis://:yszx_redis_2026@127.0.0.1:6380/0"  # 6380=deploy 映射（避让原生 6379）

    # ---- MinIO（02 D15，S3 兼容）----
    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "yszx_minio_2026"
    minio_bucket: str = "yszx-assets"
    minio_secure: bool = False

    # ---- JWT（04 §1.5 双 token，双端隔离）----
    jwt_secret_portal: str = "dev-portal-secret-change-me"
    jwt_secret_admin: str = "dev-admin-secret-change-me"
    jwt_access_ttl_minutes: int = 120
    jwt_refresh_ttl_days: int = 7
    jwt_refresh_ttl_days_remember: int = 30

    # ---- 外部服务适配器（02 D5/D17：联调期 mock）----
    ai_provider: str = "mock"
    sms_provider: str = "mock"

    # ---- 接口限流（04 §1.7 频控阈值未定稿，开发联调时与用户确认后固化到常量）----
    rate_limit_login_per_minute: int = 10
    rate_limit_register_per_hour: int = 20
    rate_limit_sms_code_per_hour: int = 30
    rate_limit_interview_per_hour: int = 10

    # ---- AI 面试每日配额（02 D12：发起计次、0 点重置，Redis 计数）----
    interview_daily_quota: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
