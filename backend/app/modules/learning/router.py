"""learning 路由（挂载于 /api/portal/v1）。

接口清单见 04 §2.1：
  /stages/{id}/questions | /questions/{id}
  POST /practice/paper | /practice/answers
  /wrong-questions*（统计卡/列表/重做/批量）
  /routes* | POST /courses/{id}/complete
题库（#16-19）、刷题练习（#20-21）、错题本（#22-28）、学习路线（#29-32）已全量实现。
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
    ReviewSetRequest,
    RouteListQuery,
    StageQuestionQuery,
    WrongBatchRequest,
    WrongListQuery,
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


# ===================== 错题本（04 §3.3 #22-28 / 需求 3.6） =====================


@router.get("/wrong-questions/stats")
async def wrong_stats(
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """统计卡 + 高频错题 Top3 + 分类下拉。"""
    return ok(await service.wrong_stats(db, ctx.student_id))


@router.get("/wrong-questions")
async def wrong_list(
    q: WrongListQuery = Depends(),
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """错题列表（状态/分类/时间筛选 + 排序 + 分页）。"""
    return ok(await service.wrong_list(db, ctx.student_id, q))


@router.post("/wrong-questions/review-set")
async def review_set(
    req: ReviewSetRequest,
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """重做题目集（默认待复习；重做判分复用 /practice/answers scene=wrongReview）。"""
    return ok(await service.review_set(db, ctx.student_id, req))


@router.post("/wrong-questions/{wrong_id}/master")
async def master_wrong(
    wrong_id: int,
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """标记已掌握（幂等；掌握单向 S10）。"""
    return ok(await service.master_wrong(db, ctx.student_id, wrong_id))


@router.delete("/wrong-questions/{wrong_id}")
async def remove_wrong(
    wrong_id: int,
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """移除错题（逻辑删除；同题再答错复活续增 S8）。"""
    return ok(await service.remove_wrong(db, ctx.student_id, wrong_id))


@router.post("/wrong-questions/batch-master")
async def batch_master(
    req: WrongBatchRequest,
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """批量标记已掌握（逐条同单条语义，整批原子执行）。"""
    return ok(await service.batch_master(db, ctx.student_id, req))


@router.post("/wrong-questions/batch-remove")
async def batch_remove(
    req: WrongBatchRequest,
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """批量移除（逐条同单条语义，整批原子执行）。"""
    return ok(await service.batch_remove(db, ctx.student_id, req))


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
