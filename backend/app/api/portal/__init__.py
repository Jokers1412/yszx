"""学员端路由聚合（前缀 /api/portal/v1，04 §2.1 共 39 个接口）。

挂载顺序即文档分组：账号 → 统计 → 内容 → 学习训练 → AI 面试。
"""
from fastapi import APIRouter

from app.modules.accounts.router import router as accounts_router
from app.modules.content.router import router as content_router
from app.modules.interview.router import router as interview_router
from app.modules.learning.router import router as learning_router
from app.modules.stats.router import router as stats_router

router = APIRouter()
router.include_router(accounts_router)
router.include_router(stats_router)
router.include_router(content_router)
router.include_router(learning_router)
router.include_router(interview_router)
