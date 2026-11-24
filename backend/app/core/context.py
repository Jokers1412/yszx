"""登录态上下文与角色常量（独立模块，避免 core 内循环依赖）。"""
from dataclasses import dataclass, field
from typing import FrozenSet

# 预置角色（02 §1.1 约束 8：预置 3 角色）
ROLE_SUPER_ADMIN = "super_admin"
ROLE_CONTENT_REVIEWER = "content_reviewer"
ROLE_OPERATOR = "operator"


@dataclass(frozen=True)
class AdminContext:
    """管理端登录态上下文（由 core.deps.get_current_admin 注入）。"""

    admin_id: int
    username: str
    role_code: str
    is_super_admin: bool
    permission_codes: FrozenSet[str] = field(default_factory=frozenset)

    def has(self, code: str) -> bool:
        return self.is_super_admin or code in self.permission_codes
