"""content 路由（/api/portal/v1 与 /api/admin/v1 双侧挂载）。

接口清单见 04：学员端 /subjects* /stages/{id}/questions /home/hot-stages；
管理端 /subjects* /stages* /courses* /questions* /interview-questions* /routes*。
学员端接口待功能开发阶段按契约补充（挂在 router）；管理端接口挂 admin_router。
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
from app.modules.content import service
from app.modules.content.schemas import (
    CourseCreate,
    CourseQuery,
    CourseUpdate,
    ImportConfirmRequest,
    RouteCreate,
    RouteItemsAdd,
    RouteItemsUpdate,
    RouteQuery,
    RouteUpdate,
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


# ===================== 管理端 · B站课程库（04 §4.4） =====================
# /courses/import/* 声明在 /courses/{course_id} 之前，避免被路径参数捕获。

@admin_router.get("/courses")
async def list_courses(
    q: CourseQuery = Depends(),
    _ctx: AdminContext = Depends(require_perm("course:view")),
    db: AsyncSession = Depends(get_db),
):
    """课程列表（筛选 + 分页 + 统计卡）。"""
    return ok(await service.list_courses(db, q))


@admin_router.get("/courses/export")
async def export_courses(
    request: Request,
    q: CourseQuery = Depends(),
    ctx: AdminContext = Depends(require_perm("course:view")),
    db: AsyncSession = Depends(get_db),
):
    """导出课程 Excel（按当前筛选；导出行为入操作审计）。"""
    filename, data = await service.export_courses_xlsx(db, ctx, q, ip=_client_ip(request))
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@admin_router.get("/courses/import/template")
async def download_import_template(
    _ctx: AdminContext = Depends(require_perm("course:view")),
):
    """下载导入模板（.xlsx 流）。"""
    data = service.build_import_template()
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=course-import-template.xlsx"},
    )


@admin_router.post("/courses/import/preview")
async def preview_course_import(
    file: UploadFile = File(...),
    _ctx: AdminContext = Depends(require_perm("course:create")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """导入预览（任一无效行整份拒绝；解析结果缓存 importToken）。"""
    data = await file.read()
    return ok(await service.preview_course_import(db, r, data, file.filename or ""))


@admin_router.post("/courses/import")
async def confirm_course_import(
    payload: ImportConfirmRequest,
    request: Request,
    ctx: AdminContext = Depends(require_perm("course:create")),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """确认导入（Excel 为权威数据源，覆盖更新）。"""
    return ok(await service.confirm_course_import(db, r, payload, ctx, ip=_client_ip(request)))


@admin_router.post("/courses", status_code=201)
async def create_course(
    payload: CourseCreate,
    request: Request,
    ctx: AdminContext = Depends(require_perm("course:create")),
    db: AsyncSession = Depends(get_db),
):
    """新增课程（bvid 冲突 → 409 BIZ_BVID_EXISTS）。"""
    return ok(await service.create_course(db, ctx, payload, ip=_client_ip(request)))


@admin_router.put("/courses/{course_id}")
async def update_course(
    course_id: int,
    payload: CourseUpdate,
    request: Request,
    ctx: AdminContext = Depends(require_perm("course:edit")),
    db: AsyncSession = Depends(get_db),
):
    """编辑课程（全量替换，关联学科整体替换）。"""
    return ok(await service.update_course(db, ctx, course_id, payload, ip=_client_ip(request)))


@admin_router.delete("/courses/{course_id}")
async def delete_course(
    course_id: int,
    request: Request,
    ctx: AdminContext = Depends(require_perm("course:delete")),
    db: AsyncSession = Depends(get_db),
):
    """删除课程（逻辑删除；引用它的路线保留引用）。"""
    return ok(await service.delete_course(db, ctx, course_id, ip=_client_ip(request)))


# ===================== 管理端 · 学习路线管理（04 §4.7） =====================

@admin_router.get("/routes")
async def list_routes(
    q: RouteQuery = Depends(),
    _ctx: AdminContext = Depends(require_perm("route:view")),
    db: AsyncSession = Depends(get_db),
):
    """路线卡片列表（筛选 + 分页）。"""
    return ok(await service.list_routes(db, q))


@admin_router.get("/routes/{route_id}")
async def get_route(
    route_id: int,
    _ctx: AdminContext = Depends(require_perm("route:view")),
    db: AsyncSession = Depends(get_db),
):
    """路线详情（课程管理页；预览由前端同数据渲染）。"""
    return ok(await service.get_route(db, route_id))


@admin_router.post("/routes", status_code=201)
async def create_route(
    payload: RouteCreate,
    request: Request,
    ctx: AdminContext = Depends(require_perm("route:create")),
    db: AsyncSession = Depends(get_db),
):
    """新建路线（含有序课程）。"""
    return ok(await service.create_route(db, ctx, payload, ip=_client_ip(request)))


@admin_router.put("/routes/{route_id}")
async def update_route(
    route_id: int,
    payload: RouteUpdate,
    request: Request,
    ctx: AdminContext = Depends(require_perm("route:edit")),
    db: AsyncSession = Depends(get_db),
):
    """编辑路线（基本信息全量更新，不含课程）。"""
    return ok(await service.update_route(db, ctx, route_id, payload, ip=_client_ip(request)))


@admin_router.delete("/routes/{route_id}")
async def delete_route(
    route_id: int,
    request: Request,
    ctx: AdminContext = Depends(require_perm("route:delete")),
    db: AsyncSession = Depends(get_db),
):
    """删除路线（逻辑删除；已学课程标记不受影响）。"""
    return ok(await service.delete_route(db, ctx, route_id, ip=_client_ip(request)))


@admin_router.post("/routes/{route_id}/items")
async def add_route_items(
    route_id: int,
    payload: RouteItemsAdd,
    request: Request,
    ctx: AdminContext = Depends(require_perm("route:edit")),
    db: AsyncSession = Depends(get_db),
):
    """从课程库添加课程（已添加的自动忽略）。"""
    return ok(await service.add_route_items(db, ctx, route_id, payload, ip=_client_ip(request)))


@admin_router.put("/routes/{route_id}/items")
async def update_route_items(
    route_id: int,
    payload: RouteItemsUpdate,
    request: Request,
    ctx: AdminContext = Depends(require_perm("route:edit")),
    db: AsyncSession = Depends(get_db),
):
    """课程排序/移除（有序全量，整体替换）。"""
    return ok(await service.update_route_items(db, ctx, route_id, payload, ip=_client_ip(request)))
