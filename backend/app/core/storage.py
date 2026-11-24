"""MinIO 对象存储封装（02 D15：S3 兼容自建，数据库仅存对象 URL）。

- 上传接口抽象：头像/Logo 等图片统一走 upload_image；
- 桶 yszx-assets 已开放匿名只读（deploy 编排），URL 可直链展示；
- 供应商可切换 OSS/云存储：替换本模块实现即可（02 §2.2）。
"""
import io
import uuid
from datetime import datetime, timezone

from minio import Minio

from app.common import constants as C
from app.common.error_codes import ErrorCode
from app.core.config import get_settings
from app.core.exceptions import BizError

_ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
}

_client: Minio | None = None


def _get_client() -> Minio:
    global _client
    if _client is None:
        settings = get_settings()
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def upload_image(data: bytes, content_type: str, subdir: str = "images") -> str:
    """上传图片对象，返回公开访问 URL。

    校验（04 §1.4）：仅 jpg/png、≤2MB；非法 → 400 PARAM_FILE_INVALID。
    """
    ext = _ALLOWED_IMAGE_TYPES.get(content_type)
    if ext is None:
        raise BizError(ErrorCode.PARAM_FILE_INVALID, "仅支持 jpg/png 图片", http_status=400)
    if len(data) > C.UPLOAD_IMAGE_MAX_BYTES:
        raise BizError(ErrorCode.PARAM_FILE_INVALID, "图片大小不能超过 2MB", http_status=400)
    if not data:
        raise BizError(ErrorCode.PARAM_FILE_INVALID, "图片内容为空", http_status=400)

    settings = get_settings()
    name = f"{subdir}/{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8]}.{ext}"
    _get_client().put_object(
        settings.minio_bucket,
        name,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return f"http://{settings.minio_endpoint}/{settings.minio_bucket}/{name}"
