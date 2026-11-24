"""students 路由（挂载于 /api/admin/v1）。接口清单见 04 §2.2 /students*（§4.8）。

学员由前台注册产生（无新增/编辑接口）；启停/删除经 Redis 使 refresh 失效（口径 S18）。
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.common.pagination import PageQuery
from app.core.context import AdminContext
from app.core.database import get_db
from app.core.rbac import require_perm
from app.core.redis import get_redis
from app.core.response import ok
from app.modules.students import service
from app.modules.students.schemas import (
    StudentBatchDelete,
    StudentBatchStatus,
    StudentQuery,
    StudentStatusPatch,
)

router = APIRouter(tags=["students"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


@router.get("/students")
async def list_students(
    q: StudentQuery = Depends(),
    _ctx: AdminContext = Depends(require_perm("student:view")),
    db: AsyncSession = Depends(get_db),
):
    """学员列表（手机号完整展示；统计随列表返回）。"""
    return ok(await service.list_students(db, q))


@router.get("/students/export")
async def export_students(
    request: Request,
    q: StudentQuery = Depends(),
    ctx: AdminContext = Depends(require_perm("student:view")),  # 导出归并「查看」
    db: AsyncSession = Depends(get_db),
):
    """导出学员列表（按当前筛选同步 xlsx 流）。"""
    filename, data = await service.export_students_xlsx(db, ctx, q, ip=_client_ip(request))
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/students/batch-status")
async def batch_student_status(
    payload: StudentBatchStatus,
    request: Request,
    ctx: AdminContext = Depends(require_perm("student:edit")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """批量启用/禁用（禁用使 refresh 失效，口径 S18）。"""
    return ok(await service.batch_student_status(db, r, ctx, payload, ip=_client_ip(request)))


@router.post("/students/batch-delete")
async def batch_delete_students(
    payload: StudentBatchDelete,
    request: Request,
    ctx: AdminContext = Depends(require_perm("student:delete")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """批量删除（逻辑删除整批）。"""
    return ok(await service.batch_delete_students(db, r, ctx, payload, ip=_client_ip(request)))


@router.get("/students/{student_id}")
async def get_student(
    student_id: int,
    _ctx: AdminContext = Depends(require_perm("student:view")),
    db: AsyncSession = Depends(get_db),
):
    """学员详情（资料 + 学习统计含已学课程数组 + 面试汇总）。"""
    return ok(await service.get_student(db, student_id))


@router.get("/students/{student_id}/interviews")
async def list_student_interviews(
    student_id: int,
    q: PageQuery = Depends(),
    _ctx: AdminContext = Depends(require_perm("student:view")),
    db: AsyncSession = Depends(get_db),
):
    """学员 AI 面试记录（分页）。"""
    return ok(await service.list_student_interviews(db, student_id, q))


@router.patch("/students/{student_id}/status")
async def patch_student_status(
    student_id: int,
    payload: StudentStatusPatch,
    request: Request,
    ctx: AdminContext = Depends(require_perm("student:edit")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """启用/禁用（禁用后学员端登录态作废，口径 S18）。"""
    return ok(await service.patch_student_status(db, r, ctx, student_id, payload, ip=_client_ip(request)))


@router.delete("/students/{student_id}")
async def delete_student(
    student_id: int,
    request: Request,
    ctx: AdminContext = Depends(require_perm("student:delete")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """删除学员（逻辑删除，手机号可重新注册）。"""
    return ok(await service.delete_student(db, r, ctx, student_id, ip=_client_ip(request)))
