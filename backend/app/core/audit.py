"""操作审计埋点（02 D13 / 04 §4 引言）。

范围：管理端全部写操作 + 登录/登出 + 导出行为；落 operation_log 表。
action_type 分类见 03（1登录类 2新增 3修改 4删除 5禁用 6其他含导出）。
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import OperationActionType
from app.modules.system.models import OperationLog


async def record_operation(
    db: AsyncSession,
    *,
    action_type: OperationActionType,
    action_desc: str,
    admin_user_id: Optional[int] = None,
    admin_username: Optional[str] = None,
    target: Optional[str] = None,
    detail: Optional[str] = None,
    ip: str = "",
) -> None:
    """写入一条操作日志（随调用方事务提交）。"""
    db.add(
        OperationLog(
            admin_user_id=admin_user_id,
            admin_username=admin_username,
            action_type=int(action_type),
            action_desc=action_desc,
            target=target,
            detail=detail,
            ip=ip,
        )
    )
