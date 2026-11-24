"""统一响应结构（04 §1.2 定稿）。

成功：{ "code": 0, "message": "success", "data": … }
失败：{ "code": "<业务码>", "message": "…", "data": … }（经 BizError/异常处理器输出）

分页（04 §1.3）：data 内 { "list": [], "total": 0, "pageNum": 1, "pageSize": 10 }，
入参 pageNum 从 1 起、pageSize 默认 10 上限 100。
"""
from typing import Any, Optional

from fastapi.responses import JSONResponse

SUCCESS_CODE = 0
SUCCESS_MESSAGE = "success"


def ok(data: Any = None, message: str = SUCCESS_MESSAGE, status_code: int = 200) -> JSONResponse:
    """成功响应（创建资源可传 status_code=201）。"""
    return JSONResponse(
        status_code=status_code,
        content={"code": SUCCESS_CODE, "message": message, "data": data},
    )
