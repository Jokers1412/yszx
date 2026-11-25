"""accounts 请求/响应模型（04 §3.1 契约）。

命名约定（04 §1.1）：JSON 字段 lowerCamelCase；时间 Asia/Shanghai 字符串；
不返回 passwordHash/deletedAt 等内部字段。
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class SmsCodeRequest(BaseModel):
    scene: Literal["register", "login", "reset"]
    phone: str = Field(pattern=r"^1\d{10}$")


class SmsCodeResult(BaseModel):
    sentAt: str  # 60s 倒计时基准（Asia/Shanghai）


class RegisterRequest(BaseModel):
    phone: str = Field(pattern=r"^1\d{10}$")
    code: str = Field(pattern=r"^\d{6}$")
    password: str = Field(min_length=6, max_length=20)


class LoginPasswordRequest(BaseModel):
    account: str = Field(min_length=1, max_length=100, description="手机号或邮箱")
    password: str = Field(min_length=1, max_length=100)
    rememberMe: bool = True


class LoginSmsRequest(BaseModel):
    phone: str = Field(pattern=r"^1\d{10}$")
    code: str = Field(pattern=r"^\d{6}$")
    rememberMe: bool = True


class PasswordResetRequest(BaseModel):
    phone: str = Field(pattern=r"^1\d{10}$")
    code: str = Field(pattern=r"^\d{6}$")
    newPassword: str = Field(min_length=6, max_length=20)


class RefreshRequest(BaseModel):
    refreshToken: str = Field(min_length=1)
    clientType: Literal["portal", "admin"]


class LogoutRequest(BaseModel):
    refreshToken: Optional[str] = Field(default=None, max_length=2000)


class ProfileUpdate(BaseModel):
    nickname: str = Field(min_length=1, max_length=50)
    email: Optional[str] = Field(default=None, max_length=100)
    gender: Literal["male", "female", "secret"] = "secret"
    avatarUrl: Optional[str] = Field(default=None, max_length=255)


class AuthUserBrief(BaseModel):
    id: int
    nickname: str
    avatarUrl: Optional[str] = None
    isAdmin: bool = False


class AuthResult(BaseModel):
    """登录/注册响应（注册即登录 ⚠️ 口径 S3）。"""

    accessToken: str
    refreshToken: str
    expiresIn: int  # access 有效期秒数
    user: AuthUserBrief


class ProfileResult(BaseModel):
    """个人基本信息（admin 账号登录时仅基础信息，isAdmin=true）。"""

    id: int
    nickname: str
    phone: str  # 完整值，前端按需求 3.3 脱敏展示（口径 S6）
    email: Optional[str] = None
    gender: Optional[str] = None  # admin 身份无性别 → null
    avatarUrl: Optional[str] = None
    isAdmin: bool = False
    createdAt: Optional[str] = None
    lastLoginAt: Optional[str] = None
