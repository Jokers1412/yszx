"""管理端 RBAC：权限码目录（9 组 33 项，04 附录 A 定稿）与鉴权依赖（04 §1.6）。

约定：
  - 服务端接口级强制校验；前端按 permissionCodes 渲染菜单/按钮；
  - super_admin 角色免检全部权限；角色管理接口仅超管可用（Q3）；
  - 权限码为代码常量（02 D10），GET /permissions 权限树即本目录数据源。
"""
from typing import Callable

from fastapi import Depends

from app.common.error_codes import ErrorCode
from app.core.context import (
    ROLE_CONTENT_REVIEWER,
    ROLE_OPERATOR,
    ROLE_SUPER_ADMIN,
    AdminContext,
)
from app.core.exceptions import BizError

__all__ = [
    "PERMISSION_TREE",
    "PERMISSION_CODES",
    "ROLE_SUPER_ADMIN",
    "ROLE_CONTENT_REVIEWER",
    "ROLE_OPERATOR",
    "AdminContext",
    "require_perm",
]

# (分组, [(权限码, 名称)])，9 组 33 项
PERMISSION_TREE: list[tuple[str, list[tuple[str, str]]]] = [
    ("题库管理", [
        ("question:view", "查看"),
        ("question:create", "新增"),
        ("question:edit", "编辑"),
        ("question:delete", "删除"),
        ("question:import", "导入"),
        ("question:export", "导出"),
        ("question:review", "审核"),
    ]),
    ("面试题库管理", [
        ("interviewbank:view", "查看"),
        ("interviewbank:edit", "编辑"),
        ("interviewbank:delete", "删除"),
        ("interviewbank:test", "检索测试"),  # 预留（D4-21 本期不实现）
    ]),
    ("用户管理", [
        ("user:view", "查看"),
        ("user:create", "新增"),
        ("user:edit", "编辑"),
        ("user:disable", "禁用"),
    ]),
    ("学习路线", [
        ("route:view", "查看"),
        ("route:create", "新增"),
        ("route:edit", "编辑"),
        ("route:delete", "删除"),
    ]),
    ("学员管理", [
        ("student:view", "查看"),
        ("student:edit", "编辑"),
        ("student:delete", "删除"),
    ]),
    ("学科管理", [
        ("subject:view", "查看"),
        ("subject:create", "新增"),
        ("subject:edit", "编辑"),
        ("subject:delete", "删除"),
    ]),
    ("课程库", [
        ("course:view", "查看"),
        ("course:create", "新增"),
        ("course:edit", "编辑"),
        ("course:delete", "删除"),
    ]),
    ("数据看板", [
        ("dashboard:view", "查看"),
    ]),
    ("系统管理", [
        ("log:view", "日志查看"),
        ("system:settings", "系统设置"),
    ]),
]

PERMISSION_CODES = frozenset(
    code for _, items in PERMISSION_TREE for code, _ in items
)


def require_perm(code: str) -> Callable:
    """接口级权限依赖：require_perm("question:edit")（与 get_current_admin 组合注入）。

    超管免检；无权限 → 403 PERM_DENIED（04 §1.6）。
    """
    if code not in PERMISSION_CODES:
        raise ValueError(f"unknown permission code: {code}")

    from app.core.deps import get_current_admin

    async def _dependency(ctx: AdminContext = Depends(get_current_admin)) -> AdminContext:
        if not ctx.has(code):
            raise BizError(ErrorCode.PERM_DENIED, "无权限执行该操作", http_status=403)
        return ctx

    return _dependency
