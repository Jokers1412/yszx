"""learning 路由（挂载于 /api/portal/v1）。

接口清单见 04 §2.1：
  /stages/{id}/questions | /questions/{id}
  POST /practice/paper | /practice/answers
  /wrong-questions*（统计卡/列表/重做/批量）
  /routes* | POST /courses/{id}/complete
学习路线（#29-32）已实现；练习/错题待后续功能开发。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import StudentContext, get_current_student
from app.core.response import ok
from app.modules.learning import service
from app.modules.learning.schemas import RouteListQuery

router = APIRouter(tags=["learning"])


# ===================== 学习路线（04 §3.3 #29-32 / 需求 3.7） =====================
# 注意：/routes/subjects 需先于 /routes/{route_id} 注册（避免被参数路由吞掉）


@router.get("/routes/subjects")
async def route_subjects(
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """学科卡片（含无路线学科，routeCount=启用路线数）。"""
    return ok(await service.route_subjects(db))


@router.get("/routes")
async def list_routes(
    q: RouteListQuery = Depends(),
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """路线列表（含进度/最近学习时间）：仅启用路线。"""
    return ok(await service.list_routes(db, ctx.student_id, q.subjectId))


@router.get("/routes/{route_id}")
async def route_detail(
    route_id: int,
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """路线详情（课程学习顺序 + 已学标记）。"""
    return ok(await service.route_detail(db, ctx.student_id, route_id))


@router.post("/courses/{course_id}/complete")
async def complete_course(
    course_id: int,
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """标记已学完（幂等；仅标记不可取消）。"""
    return ok(await service.complete_course(db, ctx.student_id, course_id))
