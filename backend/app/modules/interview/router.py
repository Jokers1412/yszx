"""interview 路由（/api/portal/v1 与 /api/admin/v1 双侧挂载）。

学员端已实现（04 §3.4 #33-38 + 回放）：
  GET /interviews/config-meta | POST /interviews 发起（配额+抽题）| POST /{id}/answers 逐题评分
  POST /{id}/finish 生成报告 | GET /{id}/report | GET /interviews 记录 | GET /{id} 回放

管理端已实现（04 §4.6 面试题库管理，interviewbank:*）：
  GET /interview-questions 列表 | GET /{id} 详情 | POST 录入 | PUT 仅主题/难度 | DELETE 逻辑删除
  导入两段式 preview/import + GET /import/template（6 列，仅读第一张工作表）
"""
from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.core.context import AdminContext
from app.core.database import get_db
from app.core.deps import StudentContext, get_current_student
from app.core.rbac import require_perm
from app.core.redis import get_redis
from app.core.response import ok
from app.modules.content.schemas import ImportConfirmRequest
from app.modules.interview import service
from app.modules.interview.schemas import (
    AnswerSubmitRequest,
    FinishRequest,
    InterviewQuestionCreate,
    InterviewQuestionQuery,
    InterviewQuestionUpdate,
    RecordsQuery,
    StartInterviewRequest,
)

router = APIRouter(tags=["interview"])
admin_router = APIRouter(tags=["interview"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


# ===================== 学员端 · AI 面试（04 §3.4） =====================
# /interviews/config-meta 须先于 /interviews/{record_id} 注册（避免被参数路由吞掉）。


@router.get("/interviews/config-meta")
async def config_meta(
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """面试配置页数据（方向/难度/题量/超时/今日剩余配额）。"""
    return ok(await service.config_meta(db, r, ctx.student_id))


@router.post("/interviews")
async def start_interview(
    req: StartInterviewRequest,
    request: Request,
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """发起面试（S1 发起即计配额；Q4 题库不足 AI 补充；S11 一次下发全部题干）。"""
    return ok(
        await service.start_interview(db, r, ctx.student_id, _client_ip(request), req)
    )


@router.post("/interviews/{record_id}/answers")
async def submit_answer(
    record_id: int,
    req: AnswerSubmitRequest,
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """提交逐题作答（AI 评分；失败 503 不落记录可重试；重复提交 409）。"""
    return ok(await service.submit_answer(db, ctx.student_id, record_id, req))


@router.post("/interviews/{record_id}/finish")
async def finish(
    record_id: int,
    req: FinishRequest,
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """结束面试并生成报告（中途结束也可生成；重复 finish 409）。"""
    return ok(await service.finish(db, ctx.student_id, record_id, req))


@router.get("/interviews/{record_id}/report")
async def get_report(
    record_id: int,
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """面试报告（W3 评分换算 + 同方向相比上次）。"""
    return ok(await service.get_report(db, ctx.student_id, record_id))


@router.get("/interviews")
async def list_records(
    q: RecordsQuery = Depends(),
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """面试记录列表 + 统计卡（仅已完成场次）。"""
    return ok(await service.list_records(db, ctx.student_id, q))


@router.get("/interviews/{record_id}")
async def get_replay(
    record_id: int,
    ctx: StudentContext = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """面试回放（S12 逐题快照重建对话流，仅本人可看）。"""
    return ok(await service.get_replay(db, ctx.student_id, record_id))


# ===================== 管理端 · 面试题库管理（04 §4.6） =====================
# /import/* 声明在 /{question_id} 之前，避免被路径参数捕获。

@admin_router.get("/interview-questions")
async def list_interview_questions(
    q: InterviewQuestionQuery = Depends(),
    _ctx: AdminContext = Depends(require_perm("interviewbank:view")),
    db: AsyncSession = Depends(get_db),
):
    """题目列表（unclassifiedOnly=只看未分类，与 topic 互斥）。"""
    return ok(await service.list_interview_questions(db, q))


@admin_router.get("/interview-questions/import/template")
async def download_interview_import_template(
    _ctx: AdminContext = Depends(require_perm("interviewbank:view")),
):
    """下载导入模板（.xlsx，6 列）。"""
    data = service.build_interview_import_template()
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=interview-import-template.xlsx"},
    )


@admin_router.post("/interview-questions/import/preview")
async def preview_interview_import(
    file: UploadFile = File(...),
    _ctx: AdminContext = Depends(require_perm("interviewbank:edit")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """导入预览（任一无效行整份拒绝；涉及学科汇总 + 告警）。"""
    data = await file.read()
    return ok(await service.preview_interview_import(db, r, data, file.filename or ""))


@admin_router.post("/interview-questions/import")
async def confirm_interview_import(
    payload: ImportConfirmRequest,
    request: Request,
    ctx: AdminContext = Depends(require_perm("interviewbank:edit")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """确认导入（来源记文件名+行号）。"""
    return ok(await service.confirm_interview_import(db, r, payload, ctx, ip=_client_ip(request)))


@admin_router.post("/interview-questions", status_code=201)
async def create_interview_question(
    payload: InterviewQuestionCreate,
    request: Request,
    ctx: AdminContext = Depends(require_perm("interviewbank:edit")),  # 归并：无「新增」权限点
    db: AsyncSession = Depends(get_db),
):
    """录入题目（sourceType=manual）。"""
    return ok(await service.create_interview_question(db, ctx, payload, ip=_client_ip(request)))


@admin_router.get("/interview-questions/{question_id}")
async def get_interview_question(
    question_id: int,
    _ctx: AdminContext = Depends(require_perm("interviewbank:view")),
    db: AsyncSession = Depends(get_db),
):
    """题目详情（全字段含参考答案）。"""
    return ok(await service.get_interview_question(db, question_id))


@admin_router.put("/interview-questions/{question_id}")
async def update_interview_question(
    question_id: int,
    payload: InterviewQuestionUpdate,
    request: Request,
    ctx: AdminContext = Depends(require_perm("interviewbank:edit")),
    db: AsyncSession = Depends(get_db),
):
    """编辑（仅主题与难度，其他字段拒收）。"""
    return ok(await service.update_interview_question(db, ctx, question_id, payload, ip=_client_ip(request)))


@admin_router.delete("/interview-questions/{question_id}")
async def delete_interview_question(
    question_id: int,
    request: Request,
    ctx: AdminContext = Depends(require_perm("interviewbank:delete")),
    db: AsyncSession = Depends(get_db),
):
    """删除（逻辑删除，风险提示按来源区分）。"""
    return ok(await service.delete_interview_question(db, ctx, question_id, ip=_client_ip(request)))
