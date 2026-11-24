"""业务异常体系与全局异常处理（04 §1.2/§1.4、api-rules §5）。

约定：
  - HTTP 状态码表达语义 + 稳定字符串业务码（04 附录 B），互不矛盾；
  - 校验失败 → 400 PARAM_VALIDATION_FAILED + data.fieldErrors；
  - 未捕获异常 → 500 SYS_INTERNAL，不泄露内部细节。
"""
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.error_codes import ErrorCode

# HTTP 状态码 → 默认业务码（HTTPException 兜底映射，04 附录 B）
_HTTP_CODE_MAP = {
    400: ErrorCode.PARAM_VALIDATION_FAILED,
    401: ErrorCode.AUTH_TOKEN_INVALID,
    403: ErrorCode.PERM_DENIED,
    404: ErrorCode.RESOURCE_NOT_FOUND,
    409: ErrorCode.BIZ_STATE_INVALID,
    423: ErrorCode.AUTH_LOCKED,
    429: ErrorCode.RATE_LIMITED,
    500: ErrorCode.SYS_INTERNAL,
}


class BizError(Exception):
    """业务异常：携带稳定业务码 + HTTP 状态码 + 可选字段级明细。"""

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = 400,
        data: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.data = data


def _payload(code: str, message: str, data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizError)
    async def _biz_error(_: Request, exc: BizError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=_payload(exc.code, exc.message, exc.data),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        field_errors = [
            {
                "field": ".".join(str(p) for p in err.get("loc", []) if p != "body"),
                "reason": err.get("msg", "参数不合法"),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=400,
            content=_payload(
                ErrorCode.PARAM_VALIDATION_FAILED,
                "参数校验失败",
                {"fieldErrors": field_errors},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODE_MAP.get(exc.status_code, ErrorCode.SYS_INTERNAL)
        detail = exc.detail
        message = detail if isinstance(detail, str) and detail else "请求失败"
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(code, message, None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        # 不泄露内部细节（api-rules §5.3）；细节进服务端日志
        import logging

        logging.getLogger("yszx").exception("未捕获异常: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_payload(ErrorCode.SYS_INTERNAL, "服务开小差了，请稍后再试", None),
        )
