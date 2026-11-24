"""content 路由（/api/portal/v1 与 /api/admin/v1 双侧挂载）。

接口清单见 04：学员端 /subjects* /stages/{id}/questions /home/hot-stages；
管理端 /subjects* /stages* /courses* /questions* /interview-questions* /routes*。
学员端接口待功能开发阶段按契约补充（挂在 router）；管理端接口挂 admin_router。
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import AdminContext
from app.core.database import get_db
from app.core.rbac import require_perm
from app.core.response import ok
from app.modules.content import service
from app.modules.content.schemas import (
    StageCreate,
    StageSort,
    StageStatusPatch,
    StageUpdate,
    SubjectCreate,
    SubjectSort,
    SubjectUpdate,
)

router = APIRouter(tags=["content"])
admin_router = APIRouter(tags=["content"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


# ===================== 管理端 · 学科管理（04 §4.3） =====================
# 注意：/subjects/sort、/stages/sort 须声明在 /{id} 路由之前，避免被路径参数捕获。

@admin_router.get("/subjects")
async def list_subjects(
    ctx: AdminContext = Depends(require_perm("subject:view")),
    db: AsyncSession = Depends(get_db),
):
    """学科+阶段列表（含统计卡与删除三态提示计数）。"""
    return ok(await service.list_subjects(db))


@admin_router.put("/subjects/sort")
async def sort_subjects(
    payload: SubjectSort,
    request: Request,
    ctx: AdminContext = Depends(require_perm("subject:edit")),
    db: AsyncSession = Depends(get_db),
):
    """学科排序（全量 id 重排 sortOrder）。"""
    return ok(await service.sort_subjects(db, ctx, payload, ip=_client_ip(request)))


@admin_router.post("/subjects", status_code=201)
async def create_subject(
    payload: SubjectCreate,
    request: Request,
    ctx: AdminContext = Depends(require_perm("subject:create")),
    db: AsyncSession = Depends(get_db),
):
    """新增学科（重名 → 409 BIZ_SUBJECT_NAME_EXISTS）。"""
    return ok(await service.create_subject(db, ctx, payload, ip=_client_ip(request)))


@admin_router.put("/subjects/{subject_id}")
async def update_subject(
    subject_id: int,
    payload: SubjectUpdate,
    request: Request,
    ctx: AdminContext = Depends(require_perm("subject:edit")),
    db: AsyncSession = Depends(get_db),
):
    """编辑学科（全量替换）。"""
    return ok(await service.update_subject(db, ctx, subject_id, payload, ip=_client_ip(request)))


@admin_router.delete("/subjects/{subject_id}")
async def delete_subject(
    subject_id: int,
    request: Request,
    ctx: AdminContext = Depends(require_perm("subject:delete")),
    db: AsyncSession = Depends(get_db),
):
    """删除学科（逻辑删除不级联，03 S1）。"""
    return ok(await service.delete_subject(db, ctx, subject_id, ip=_client_ip(request)))


@admin_router.put("/stages/sort")
async def sort_stages(
    payload: StageSort,
    request: Request,
    ctx: AdminContext = Depends(require_perm("subject:edit")),
    db: AsyncSession = Depends(get_db),
):
    """阶段排序（同学科全量 id 重排）。"""
    return ok(await service.sort_stages(db, ctx, payload, ip=_client_ip(request)))


@admin_router.post("/stages", status_code=201)
async def create_stage(
    payload: StageCreate,
    request: Request,
    ctx: AdminContext = Depends(require_perm("subject:create")),
    db: AsyncSession = Depends(get_db),
):
    """新增阶段。"""
    return ok(await service.create_stage(db, ctx, payload, ip=_client_ip(request)))


@admin_router.put("/stages/{stage_id}")
async def update_stage(
    stage_id: int,
    payload: StageUpdate,
    request: Request,
    ctx: AdminContext = Depends(require_perm("subject:edit")),
    db: AsyncSession = Depends(get_db),
):
    """编辑阶段（同新增字段，全量）。"""
    return ok(await service.update_stage(db, ctx, stage_id, payload, ip=_client_ip(request)))


@admin_router.patch("/stages/{stage_id}/status")
async def patch_stage_status(
    stage_id: int,
    payload: StageStatusPatch,
    request: Request,
    ctx: AdminContext = Depends(require_perm("subject:edit")),
    db: AsyncSession = Depends(get_db),
):
    """阶段启用/禁用。"""
    return ok(await service.patch_stage_status(db, ctx, stage_id, payload, ip=_client_ip(request)))


@admin_router.delete("/stages/{stage_id}")
async def delete_stage(
    stage_id: int,
    request: Request,
    ctx: AdminContext = Depends(require_perm("subject:delete")),
    db: AsyncSession = Depends(get_db),
):
    """删除阶段（逻辑删除不级联，03 S1）。"""
    return ok(await service.delete_stage(db, ctx, stage_id, ip=_client_ip(request)))
