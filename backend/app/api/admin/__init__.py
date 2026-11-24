"""管理端路由聚合（前缀 /api/admin/v1，04 §2.2 共 82 个接口）。

挂载顺序即文档分组：系统管理（含登录）→ 数据看板 → 内容管理 → 学员管理。
content/stats 为双端共用模块，其 admin 侧接口在功能开发时经独立 router 挂载于此。
"""
from fastapi import APIRouter

from app.modules.stats.router import router as stats_router
from app.modules.students.router import router as students_router
from app.modules.system.router import router as system_router

router = APIRouter()
router.include_router(system_router)
router.include_router(stats_router)
router.include_router(students_router)
