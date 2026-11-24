"""stats 路由（挂载于 /api/portal/v1，04 §3.2 首页 /home/*）。

/profile/stats 与 admin /dashboard* 后续功能补齐（本阶段仅首页数据）。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import StudentContext, get_current_student
from app.core.response import ok
from app.modules.stats import service

router = APIRouter(tags=["stats"])


@router.get("/home/stats")
async def home_stats(db: AsyncSession = Depends(get_db)):
    """首页 Hero 平台数据（游客）：三项实时统计 + 好评率静态值。"""
    return ok(await service.home_stats(db))


@router.get("/home/learn-stats")
async def home_learn_stats(
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """学习统计 + 近 7 日趋势（登录，03 §5.2 口径）。"""
    return ok(await service.learn_stats(db, ctx.student_id))


@router.get("/home/hot-stages")
async def home_hot_stages(db: AsyncSession = Depends(get_db)):
    """热门阶段（游客）：启用阶段、按 sort_order、上限 12。"""
    return ok(await service.hot_stages(db))
