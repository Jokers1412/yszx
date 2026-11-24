"""system 请求/响应模型（04 §4.1 认证、§4.9-4.12 用户/角色/日志/设置契约）。

命名约定（04 §1.1）：JSON lowerCamelCase；不返回 passwordHash/deletedAt 等内部字段。
注：admin_user 表无 nickname 列，响应 nickname 为派生值（= username，04 §4.1 契约字段）。
"""
from typing import Optional

from pydantic import BaseModel, Field

from app.common.pagination import PageQuery


# ---------- 认证（04 §4.1）----------

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50, description="管理员账号")
    password: str = Field(min_length=1, max_length=72, description="登录密码（bcrypt 明文上限 72 字节）")
    rememberMe: bool = Field(default=True, description="记住登录状态（refresh 30d/7d）")


class AdminUserBrief(BaseModel):
    id: int
    username: str
    nickname: str  # 派生值（=username）
    avatarUrl: Optional[str] = None
    roleName: str
    isSuper: bool


class LoginResult(BaseModel):
    accessToken: str
    refreshToken: str
    expiresIn: int  # access 有效期（秒）
    user: AdminUserBrief


class LogoutRequest(BaseModel):
    refreshToken: Optional[str] = Field(default=None, description="可选，一并作废")


class ProfileResult(BaseModel):
    user: AdminUserBrief
    permissionCodes: list[str]  # 超管返回全量 33 码（04 §4.1）


# ---------- 用户管理（04 §4.9）----------

class UserQuery(PageQuery):
    keyword: Optional[str] = Field(default=None, max_length=50, description="用户名/手机号模糊")
    roleCode: Optional[str] = Field(default=None, max_length=50)
    status: Optional[str] = Field(default=None, pattern="^(enabled|disabled)$")


class UserItem(BaseModel):
    id: int
    username: str
    nickname: str  # 派生值（=username）
    avatarUrl: Optional[str] = None
    phone: str
    roleCode: str
    roleName: str
    status: str  # enabled | disabled
    lastLoginAt: Optional[str] = None  # Asia/Shanghai 字符串（04 §1.1）


class UserRecentLog(BaseModel):
    action: str
    at: str


class UserDetail(UserItem):
    email: Optional[str] = None
    createdAt: str
    recentLogs: list[UserRecentLog]


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    phone: str = Field(pattern=r"^1\d{10}$", description="11 位手机号")
    email: Optional[str] = Field(default=None, max_length=100)
    roleCode: str = Field(min_length=1, max_length=50, description="不含 super_admin（A5）")
    password: str = Field(min_length=6, max_length=20)
    status: str = Field(default="enabled", pattern="^(enabled|disabled)$")


class UserUpdate(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    phone: str = Field(pattern=r"^1\d{10}$")
    email: Optional[str] = Field(default=None, max_length=100)
    roleCode: str = Field(min_length=1, max_length=50)
    password: Optional[str] = Field(default=None, min_length=6, max_length=20, description="空=不修改")
    status: str = Field(default="enabled", pattern="^(enabled|disabled)$")


class UserStatusPatch(BaseModel):
    status: str = Field(pattern="^(enabled|disabled)$")


class BatchIds(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)


class BatchStatusPatch(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)
    status: str = Field(pattern="^(enabled|disabled)$")


# ---------- 角色管理（04 §4.10，仅超管）----------

class RoleItem(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    isPreset: bool
    userCount: int
    permissionTags: list[str]  # 全部权限/暂无权限/「组名·权限名」标签（需求 4.5.2）


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    code: str = Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$", description="小写字母开头")
    description: Optional[str] = Field(default=None, max_length=255)


class RoleUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    description: Optional[str] = Field(default=None, max_length=255)


class RolePermissionsUpdate(BaseModel):
    permissionCodes: list[str] = Field(default_factory=list, max_length=100, description="全量覆盖（03 S2）")


class PermissionGroup(BaseModel):
    group: str
    items: list[dict]  # [{code, name}]


# ---------- 操作日志（04 §4.11）----------

class LogQuery(PageQuery):
    keyword: Optional[str] = Field(default=None, max_length=100, description="用户/操作/目标模糊")
    actionType: Optional[str] = Field(
        default=None, pattern="^(all|login|create|update|delete|disable|other)$"
    )
    dateFrom: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    dateTo: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    adminUserId: Optional[int] = None


class LogItem(BaseModel):
    id: int
    adminUsername: Optional[str] = None
    actionType: str  # login|create|update|delete|disable|other
    actionDesc: str
    target: Optional[str] = None
    detail: Optional[str] = None
    ip: str
    createdAt: str


class LogDetail(LogItem):
    adminUserId: Optional[int] = None


# ---------- 系统设置（04 §4.12）----------

class SettingsResult(BaseModel):
    platformName: str
    platformDescription: Optional[str] = None
    logoUrl: Optional[str] = None
    defaultAvatarUrl: Optional[str] = None


class SettingsUpdate(BaseModel):
    platformName: str = Field(min_length=1, max_length=50)
    platformDescription: Optional[str] = Field(default=None, max_length=500)
    logoUrl: Optional[str] = Field(default=None, max_length=255)
    defaultAvatarUrl: Optional[str] = Field(default=None, max_length=255)
