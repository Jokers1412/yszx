"""content 路由（/api/portal/v1 与 /api/admin/v1 双侧挂载）。

接口清单见 04：学员端 /subjects* /stages/{id}/questions /home/hot-stages；
管理端 /subjects* /stages* /courses* /questions* /interview-questions* /routes*。
待功能开发阶段按契约实现。
"""
from fastapi import APIRouter

router = APIRouter(tags=["content"])
