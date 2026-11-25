"""短信适配器（02 D14：供应商抽象，联调期 Mock）。

Mock 实现仅打印日志（开发时从后端控制台查看验证码）；
接入真实供应商（阿里云/腾讯云等）时替换实现，接口与调用方不变。
"""
import logging

from app.core.config import get_settings

logger = logging.getLogger("app.sms")


async def send_sms_code(phone: str, code: str) -> None:
    """发送短信验证码。"""
    provider = get_settings().sms_provider
    if provider == "mock":
        # ⚠️ Mock 不真发短信；验证码仅打印于此（契约不回传验证码本体）
        logger.warning("【Mock 短信】phone=%s code=%s（sms_provider=mock，未真实发送）", phone, code)
        return
    raise RuntimeError(f"unsupported sms provider: {provider}")
