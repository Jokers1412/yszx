"""stats 路由（portal 挂 /api/portal/v1；admin 挂 /api/admin/v1）。

portal：04 §3.2 首页 /home/* + §3.1 /profile/stats；
admin：04 §4.2 数据看板 /dashboard*（dashboard:view）。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import AdminContext
from app.core.database import get_db
from app.core.deps import StudentContext, get_current_student
from app.core.rbac import require_perm
from app.core.response import ok
from app.modules.stats import service
from app.modules.stats.schemas import UserGrowthQuery

router = APIRouter(tags=["stats"])
admin_router = APIRouter(tags=["stats"])


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


@router.get("/profile/stats")
async def profile_stats(
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """个人学习数据（登录，03 §5.2 口径；admin 身份返回全 0）。"""
    return ok(await service.profile_stats(db, ctx.student_id))


# ===================== 管理端 · 数据看板（04 §4.2） =====================


@admin_router.get("/dashboard")
async def dashboard(
    _ctx: AdminContext = Depends(require_perm("dashboard:view")),
    db: AsyncSession = Depends(get_db),
):
    """看板汇总：卡片+趋势文案+题目学科分布+最近活动。"""
    return ok(await service.dashboard(db))


@admin_router.get("/dashboard/user-growth")
async def user_growth(
    q: UserGrowthQuery = Depends(),
    _ctx: AdminContext = Depends(require_perm("dashboard:view")),
    db: AsyncSession = Depends(get_db),
):
    """用户增长趋势（days=7|30|90，按注册日期沪日界计数）。"""
    return ok(await service.user_growth(db, int(q.days)))
