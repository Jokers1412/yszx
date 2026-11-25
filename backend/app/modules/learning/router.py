"""learning 路由（挂载于 /api/portal/v1）。

接口清单见 04 §2.1：
  /stages/{id}/questions | /questions/{id}
  POST /practice/paper | /practice/answers
  /wrong-questions*（统计卡/列表/重做/批量）
  /routes* | POST /courses/{id}/complete
题库/学习路线（#16-19/#29-32）与刷题练习（#20-21）已实现；错题待后续功能开发。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import StudentContext, get_current_student
from app.core.response import ok
from app.modules.learning import service
from app.modules.learning.schemas import (
    PracticeAnswerRequest,
    PracticePaperRequest,
    RouteListQuery,
    StageQuestionQuery,
)

router = APIRouter(tags=["learning"])


# ===================== 题库中心（04 §3.3 #18-19 / 需求 3.4） =====================


@router.get("/stages/{stage_id}/questions")
async def stage_questions(
    stage_id: int,
    q: StageQuestionQuery = Depends(),
    _ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """阶段题目列表（筛选/分页；列表不含正确答案，防作弊）。"""
    return ok(await service.stage_questions(db, stage_id, q))


@router.get("/questions/{question_id}")
async def question_detail(
    question_id: int,
    _ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """题目详情（查看解析：正确答案+解析）。"""
    return ok(await service.question_detail(db, question_id))


# ===================== 刷题练习（04 §3.3 #20-21 / 需求 3.5） =====================


@router.post("/practice/paper")
async def practice_paper(
    req: PracticePaperRequest,
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """练习出题（一次下发全部题干，不含答案）。"""
    return ok(await service.create_paper(db, ctx.student_id, req))


@router.post("/practice/answers")
async def practice_answers(
    req: PracticeAnswerRequest,
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """提交作答判分（客观题即时判分；简答 AI 批改，失败 503 可重试）。"""
    return ok(await service.submit_answer(db, ctx.student_id, req))


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
