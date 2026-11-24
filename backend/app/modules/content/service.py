"""content 业务服务（04 §4.3 学科管理已实现；课程/题目/路线后续补充）。

职责：学科/阶段维护、课程库（多对多学科、bvid 唯一、导入覆盖语义）、
题目状态流转与审核（严格流转图）、面试题库（来源标记 Excel 文件名+行号）、
路线编排与发布；向 learning/interview 提供内容查询 service 接口（02 §3.3）。

学科管理口径：
  - 计数按有效行过滤（deleted_at IS NULL），题目经所属阶段归属学科（03 §5.1）；
  - 删除不级联（03 S1）：仅标记父行，子级随父过滤隐藏；
  - 排序号 sort_order 1 起连续重排（越小越靠前），新增/编辑的 sortOrder 为目标位置。
"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import THEME_COLOR_PALETTE
from app.common.enums import EnableStatus, OperationActionType
from app.common.error_codes import ErrorCode
from app.common.utils import utc_now
from app.core.audit import record_operation
from app.core.context import AdminContext
from app.core.exceptions import BizError
from app.modules.content.models import Course, CourseSubject, Question, Route, Stage, Subject
from app.modules.content.schemas import (
    StageCreate,
    StageSort,
    StageStatusPatch,
    StageUpdate,
    SubjectCreate,
    SubjectSort,
    SubjectUpdate,
)


# ===================== 通用辅助 =====================


def _theme_color(value: str) -> str:
    if value not in THEME_COLOR_PALETTE:
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "主题颜色须为预置色板取值", http_status=400)
    return value


def _target_index(sort_order: Optional[int], length: int) -> int:
    """sortOrder 为目标位置（1 起，0 同 1）；缺省追加末尾。返回插入下标。"""
    if sort_order is None:
        return length
    return min(max(sort_order - 1, 0), length)


def _renumber(rows: list) -> None:
    """按当前列表顺序回写 sort_order = 1..n（对象已加载，随 flush 批量落库）。"""
    for i, row in enumerate(rows):
        row.sort_order = i + 1


async def _active_subjects(db: AsyncSession) -> list[Subject]:
    return list(
        (
            await db.execute(
                select(Subject)
                .where(Subject.deleted_at.is_(None))
                .order_by(Subject.sort_order, Subject.id)
            )
        ).scalars()
    )


async def _active_stages_of(db: AsyncSession, subject_id: int) -> list[Stage]:
    return list(
        (
            await db.execute(
                select(Stage)
                .where(Stage.subject_id == subject_id, Stage.deleted_at.is_(None))
                .order_by(Stage.sort_order, Stage.id)
            )
        ).scalars()
    )


async def _require_subject(db: AsyncSession, subject_id: int) -> Subject:
    subject = (
        await db.execute(select(Subject).where(Subject.id == subject_id, Subject.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if subject is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "学科不存在", http_status=404)
    return subject


async def _require_stage(db: AsyncSession, stage_id: int) -> Stage:
    stage = (
        await db.execute(select(Stage).where(Stage.id == stage_id, Stage.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if stage is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "阶段不存在", http_status=404)
    return stage


async def _check_subject_name(db: AsyncSession, name: str, exclude_id: Optional[int] = None) -> None:
    stmt = select(Subject.id).where(Subject.name == name, Subject.deleted_at.is_(None))
    if exclude_id is not None:
        stmt = stmt.where(Subject.id != exclude_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise BizError(ErrorCode.BIZ_SUBJECT_NAME_EXISTS, "学科名称已存在", http_status=409)


# ===================== 学科（04 §4.3） =====================


async def list_subjects(db: AsyncSession) -> dict:
    """学科+阶段列表（含删除三态提示所需计数，前端二次确认直接使用本响应）。"""
    subjects = await _active_subjects(db)
    stages = list(
        (
            await db.execute(
                select(Stage)
                .where(Stage.deleted_at.is_(None))
                .order_by(Stage.subject_id, Stage.sort_order, Stage.id)
            )
        ).scalars()
    )
    # 计数一次性聚合，避免逐行查询（开发规范 §5.9）
    stage_q_counts: dict[int, int] = dict(
        (
            await db.execute(
                select(Question.stage_id, func.count(Question.id))
                .where(Question.deleted_at.is_(None))
                .group_by(Question.stage_id)
            )
        ).all()
    )
    course_counts: dict[int, int] = dict(
        (
            await db.execute(
                select(CourseSubject.subject_id, func.count(CourseSubject.id))
                .join(Course, Course.id == CourseSubject.course_id)
                .where(Course.deleted_at.is_(None))
                .group_by(CourseSubject.subject_id)
            )
        ).all()
    )
    route_counts: dict[int, int] = dict(
        (
            await db.execute(
                select(Route.subject_id, func.count(Route.id))
                .where(Route.deleted_at.is_(None))
                .group_by(Route.subject_id)
            )
        ).all()
    )

    stages_by_subject: dict[int, list[Stage]] = {}
    for st in stages:
        stages_by_subject.setdefault(st.subject_id, []).append(st)

    subject_items = []
    for s in subjects:
        st_rows = stages_by_subject.get(s.id, [])
        subject_items.append(
            {
                "id": s.id,
                "name": s.name,
                "icon": s.icon,
                "description": s.description,
                "sortOrder": s.sort_order,
                "themeColor": s.theme_color,
                "courseCount": course_counts.get(s.id, 0),
                "routeCount": route_counts.get(s.id, 0),
                "questionCount": sum(stage_q_counts.get(st.id, 0) for st in st_rows),
                "stages": [
                    {
                        "id": st.id,
                        "name": st.name,
                        "icon": st.icon,
                        "sortOrder": st.sort_order,
                        "status": EnableStatus(st.status).api,
                        "questionCount": stage_q_counts.get(st.id, 0),
                    }
                    for st in st_rows
                ],
            }
        )

    return {
        "cards": {
            "total": len(subjects),
            "withStages": sum(1 for it in subject_items if it["stages"]),
            "stageTotal": len(stages),
            "questionTotal": sum(stage_q_counts.get(st.id, 0) for st in stages),
        },
        "list": subject_items,
    }


async def create_subject(
    db: AsyncSession, ctx: AdminContext, payload: SubjectCreate, ip: str
) -> dict:
    _theme_color(payload.themeColor)
    await _check_subject_name(db, payload.name)

    subject = Subject(
        name=payload.name,
        icon=payload.icon,
        description=payload.description,
        theme_color=payload.themeColor,
        sort_order=0,
    )
    db.add(subject)
    await db.flush()

    rows = await _active_subjects(db)  # 含新行
    rows = [r for r in rows if r.id != subject.id]
    rows.insert(_target_index(payload.sortOrder, len(rows)), subject)
    _renumber(rows)

    await record_operation(
        db,
        action_type=OperationActionType.CREATE,
        action_desc="新增学科",
        target=f"学科「{payload.name}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"id": subject.id}


async def update_subject(
    db: AsyncSession, ctx: AdminContext, subject_id: int, payload: SubjectUpdate, ip: str
) -> dict:
    subject = await _require_subject(db, subject_id)
    _theme_color(payload.themeColor)
    await _check_subject_name(db, payload.name, exclude_id=subject_id)

    subject.name = payload.name
    subject.icon = payload.icon
    subject.description = payload.description
    subject.theme_color = payload.themeColor

    if payload.sortOrder is not None:
        rows = [r for r in await _active_subjects(db) if r.id != subject.id]
        rows.insert(_target_index(payload.sortOrder, len(rows)), subject)
        _renumber(rows)

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="编辑学科",
        target=f"学科「{payload.name}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def delete_subject(
    db: AsyncSession, ctx: AdminContext, subject_id: int, ip: str
) -> dict:
    subject = await _require_subject(db, subject_id)
    subject.deleted_at = utc_now()  # 逻辑删除不级联（03 S1）：子级随父过滤隐藏

    await record_operation(
        db,
        action_type=OperationActionType.DELETE,
        action_desc="删除学科",
        target=f"学科「{subject.name}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def sort_subjects(
    db: AsyncSession, ctx: AdminContext, payload: SubjectSort, ip: str
) -> dict:
    rows = await _active_subjects(db)
    current_ids = {r.id for r in rows}
    if len(payload.orderedIds) != len(set(payload.orderedIds)) or set(payload.orderedIds) != current_ids:
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "orderedIds 须为全部学科 id 且不重复", http_status=400)

    by_id = {r.id: r for r in rows}
    ordered = [by_id[i] for i in payload.orderedIds]
    _renumber(ordered)

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="学科排序",
        target=f"{len(ordered)} 个学科",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


# ===================== 阶段（04 §4.3） =====================


async def create_stage(
    db: AsyncSession, ctx: AdminContext, payload: StageCreate, ip: str
) -> dict:
    subject = await _require_subject(db, payload.subjectId)

    stage = Stage(
        subject_id=subject.id,
        name=payload.name,
        icon=payload.icon,  # 留空由前端展示默认 📌
        sort_order=0,
    )
    db.add(stage)
    await db.flush()

    rows = [r for r in await _active_stages_of(db, subject.id) if r.id != stage.id]
    rows.insert(_target_index(payload.sortOrder, len(rows)), stage)
    _renumber(rows)

    await record_operation(
        db,
        action_type=OperationActionType.CREATE,
        action_desc="新增阶段",
        target=f"阶段「{payload.name}」",
        detail=f"所属学科「{subject.name}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"id": stage.id}


async def update_stage(
    db: AsyncSession, ctx: AdminContext, stage_id: int, payload: StageUpdate, ip: str
) -> dict:
    stage = await _require_stage(db, stage_id)
    subject = await _require_subject(db, payload.subjectId)

    stage.name = payload.name
    stage.icon = payload.icon
    stage.subject_id = subject.id

    if payload.sortOrder is not None:
        rows = [r for r in await _active_stages_of(db, subject.id) if r.id != stage.id]
        rows.insert(_target_index(payload.sortOrder, len(rows)), stage)
        _renumber(rows)

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="编辑阶段",
        target=f"阶段「{payload.name}」",
        detail=f"所属学科「{subject.name}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def patch_stage_status(
    db: AsyncSession, ctx: AdminContext, stage_id: int, payload: StageStatusPatch, ip: str
) -> dict:
    stage = await _require_stage(db, stage_id)
    stage.status = int(EnableStatus.from_api(payload.status))
    label = "启用" if payload.status == "enabled" else "禁用"

    await record_operation(
        db,
        action_type=OperationActionType.DISABLE,
        action_desc=f"{label}阶段",
        target=f"阶段「{stage.name}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def delete_stage(
    db: AsyncSession, ctx: AdminContext, stage_id: int, ip: str
) -> dict:
    stage = await _require_stage(db, stage_id)
    stage.deleted_at = utc_now()  # 逻辑删除不级联（03 S1）

    await record_operation(
        db,
        action_type=OperationActionType.DELETE,
        action_desc="删除阶段",
        target=f"阶段「{stage.name}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def sort_stages(
    db: AsyncSession, ctx: AdminContext, payload: StageSort, ip: str
) -> dict:
    subject = await _require_subject(db, payload.subjectId)
    rows = await _active_stages_of(db, subject.id)
    current_ids = {r.id for r in rows}
    if len(payload.orderedIds) != len(set(payload.orderedIds)) or set(payload.orderedIds) != current_ids:
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "orderedIds 须为该学科全部阶段 id 且不重复", http_status=400)

    by_id = {r.id: r for r in rows}
    ordered = [by_id[i] for i in payload.orderedIds]
    _renumber(ordered)

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="阶段排序",
        target=f"学科「{subject.name}」下 {len(ordered)} 个阶段",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}
