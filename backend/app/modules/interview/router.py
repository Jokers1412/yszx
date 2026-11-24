"""interview 路由（/api/portal/v1 与 /api/admin/v1 双侧挂载）。

学员端接口清单见 04 §2.1（/interviews* 共 7 个）：
  发起面试（配额校验+抽题）| 提交作答（逐题评分）| finish | 报告 | 记录列表/详情/回放
待功能开发阶段按契约实现（挂在 router）。

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
from app.core.rbac import require_perm
from app.core.redis import get_redis
from app.core.response import ok
from app.modules.content.schemas import ImportConfirmRequest
from app.modules.interview import service
from app.modules.interview.schemas import (
    InterviewQuestionCreate,
    InterviewQuestionQuery,
    InterviewQuestionUpdate,
)

router = APIRouter(tags=["interview"])
admin_router = APIRouter(tags=["interview"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


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
