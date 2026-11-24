"""accounts 路由（挂载于 /api/portal/v1）。

接口清单见 04 §2.1：
  POST /auth/sms-code | /auth/register | /auth/login/password | /auth/login/sms
  POST /auth/password/reset | /auth/refresh | /auth/logout
  GET/PUT /profile | POST /profile/avatar
待功能开发阶段按契约实现（基础工程阶段仅注册路由骨架）。
"""
from fastapi import APIRouter

router = APIRouter(tags=["accounts"])
