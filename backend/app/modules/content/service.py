"""content 业务服务（04 §4.3 学科管理、§4.4 B站课程库、§4.7 学习路线管理已实现；题目后续补充）。

职责：学科/阶段维护、课程库（多对多学科、bvid 唯一、导入覆盖语义）、
题目状态流转与审核（严格流转图）、面试题库（来源标记 Excel 文件名+行号）、
路线编排与发布；向 learning/interview 提供内容查询 service 接口（02 §3.3）。

学科管理口径：
  - 计数按有效行过滤（deleted_at IS NULL），题目经所属阶段归属学科（03 §5.1）；
  - 删除不级联（03 S1）：仅标记父行，子级随父过滤隐藏；
  - 排序号 sort_order 1 起连续重排（越小越靠前），新增/编辑的 sortOrder 为目标位置。

课程库口径：
  - 列表顺序（03 §5.2 S5 / 需求 4.3.2）：sort_seq 升序 = 导入批次（批次先后+Excel 行序）
    在前、非导入（种子/手动）在后且最新在前（手动新增取当前最小序值-1）；
  - 导入两段式（04 §4.4）：preview 解析缓存 importToken（Redis TTL），confirm 全量落库；
    Excel 为权威数据源、覆盖更新（bvid > 名称+来源 匹配）、关联学科整体替换（03 S2）。
"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import (
    COURSE_IMPORT_PREVIEW_ROWS,
    COURSE_IMPORT_TOKEN_TTL_SECONDS,
    EXPORT_MAX_ROWS,
    OTHER_SUBJECT_NAME,
    THEME_COLOR_PALETTE,
    UPLOAD_EXCEL_MAX_BYTES,
)
from app.common.enums import CourseSource, EnableStatus, OperationActionType
from app.common.error_codes import ErrorCode
from app.common.utils import to_shanghai, utc_now
from app.core.audit import record_operation
from app.core.context import AdminContext
from app.core.exceptions import BizError
from app.modules.content.models import (
    Course,
    CourseSubject,
    Question,
    Route,
    RouteItem,
    Stage,
    Subject,
)
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
    subject_ids = [s.id for s in subjects]
    # 阶段随父过滤隐藏（03 S1）：仅统计有效学科下的阶段，已删学科的子级不外显不计数
    stages = (
        list(
            (
                await db.execute(
                    select(Stage)
                    .where(Stage.deleted_at.is_(None), Stage.subject_id.in_(subject_ids))
                    .order_by(Stage.subject_id, Stage.sort_order, Stage.id)
                )
            ).scalars()
        )
        if subject_ids
        else []
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


# ===================== B站课程库（04 §4.4） =====================

# sort_seq 分段（03 §5.2 S5）：导入批次占低段位升序追加；非导入占 ≥BASE 段位、
# 手动新增取当前最小-1（最新在前）；列表 ORDER BY sort_seq ASC。
_MANUAL_SORT_BASE = 10**12
_IMPORT_TOKEN_PREFIX = "course:import:"


async def _next_import_seq(db: AsyncSession) -> int:
    max_seq = (
        await db.execute(
            select(func.max(Course.sort_seq)).where(Course.sort_seq < _MANUAL_SORT_BASE)
        )
    ).scalar()
    return 1 if max_seq is None else max_seq + 1


async def _next_manual_sort_seq(db: AsyncSession) -> int:
    min_seq = (
        await db.execute(
            select(func.min(Course.sort_seq)).where(Course.sort_seq >= _MANUAL_SORT_BASE)
        )
    ).scalar()
    return _MANUAL_SORT_BASE if min_seq is None else min_seq - 1


async def _other_subject(db: AsyncSession) -> Optional[Subject]:
    return (
        await db.execute(
            select(Subject).where(
                Subject.name == OTHER_SUBJECT_NAME, Subject.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()


async def _validate_course_subjects(db: AsyncSession, subject_ids: list[int]) -> list[Subject]:
    """所属学科校验：去重、有效存在；含「其他学科」时仅可单选（04 §4.4 表单约束）。"""
    if len(subject_ids) != len(set(subject_ids)):
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "所属学科不可重复", http_status=400)
    rows = list(
        (
            await db.execute(
                select(Subject).where(
                    Subject.id.in_(subject_ids), Subject.deleted_at.is_(None)
                )
            )
        ).scalars()
    )
    by_id = {s.id: s for s in rows}
    if any(i not in by_id for i in subject_ids):
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "存在无效的所属学科", http_status=400)
    other = await _other_subject(db)
    if other is not None and other.id in subject_ids and len(subject_ids) > 1:
        raise BizError(
            ErrorCode.PARAM_VALIDATION_FAILED,
            "「其他学科」不可与其他学科同时选择",
            http_status=400,
        )
    return [by_id[i] for i in subject_ids]


async def _set_course_subjects(db: AsyncSession, course_id: int, ordered_ids: list[int]) -> None:
    """关联学科整体替换（03 S2 编辑替换）：第一个=主学科。"""
    from sqlalchemy import delete as sa_delete

    await db.execute(sa_delete(CourseSubject).where(CourseSubject.course_id == course_id))
    for i, sid in enumerate(ordered_ids):
        db.add(CourseSubject(course_id=course_id, subject_id=sid, is_primary=1 if i == 0 else 0))


async def _check_bvid(db: AsyncSession, bvid: Optional[str], exclude_id: Optional[int] = None) -> None:
    if not bvid:
        return
    stmt = select(Course.id).where(Course.bvid == bvid, Course.deleted_at.is_(None))
    if exclude_id is not None:
        stmt = stmt.where(Course.id != exclude_id)
    if (await db.execute(stmt)).scalar_one_or_none() is not None:
        raise BizError(ErrorCode.BIZ_BVID_EXISTS, "BV号已存在", http_status=409)


async def _route_ref_counts(db: AsyncSession, course_ids: list[int]) -> dict[int, int]:
    """课程被有效路线引用的次数（删除确认提示 / 导入影响面）。"""
    if not course_ids:
        return {}
    rows = (
        await db.execute(
            select(RouteItem.course_id, func.count(RouteItem.id))
            .join(Route, Route.id == RouteItem.route_id)
            .where(Route.deleted_at.is_(None), RouteItem.course_id.in_(course_ids))
            .group_by(RouteItem.course_id)
        )
    ).all()
    return dict(rows)


def _course_filters(q: CourseQuery) -> list:
    """列表/导出共用筛选条件。"""
    filters = [Course.deleted_at.is_(None)]
    if q.keyword:
        filters.append(Course.name.like(f"%{q.keyword.strip()}%"))
    if q.source and q.source != "all":
        filters.append(Course.source == int(CourseSource.from_api(q.source)))
    if q.subjectId:
        filters.append(
            Course.id.in_(
                select(CourseSubject.course_id).where(CourseSubject.subject_id == q.subjectId)
            )
        )
    return filters


async def list_courses(db: AsyncSession, q: CourseQuery) -> dict:
    """课程列表（分页 + 统计卡）；列表 ORDER BY sort_seq ASC（03 §5.2 S5）。"""
    filters = _course_filters(q)

    total = (
        await db.execute(select(func.count(Course.id)).where(*filters))
    ).scalar() or 0
    rows = list(
        (
            await db.execute(
                select(Course)
                .where(*filters)
                .order_by(Course.sort_seq, Course.id)
                .offset(q.offset)
                .limit(q.limit)
            )
        ).scalars()
    )

    # 关联学科一次性取回（避免 N+1）
    course_ids = [c.id for c in rows]
    links: dict[int, list[CourseSubject]] = {}
    subject_names: dict[int, str] = {}
    if course_ids:
        link_rows = list(
            (
                await db.execute(
                    select(CourseSubject)
                    .where(CourseSubject.course_id.in_(course_ids))
                    .order_by(CourseSubject.course_id, CourseSubject.is_primary.desc(), CourseSubject.id)
                )
            ).scalars()
        )
        for lk in link_rows:
            links.setdefault(lk.course_id, []).append(lk)
        sub_rows = (
            await db.execute(select(Subject.id, Subject.name).where(Subject.deleted_at.is_(None)))
        ).all()
        subject_names = dict(sub_rows)
    ref_counts = await _route_ref_counts(db, course_ids)

    items = [
        {
            "id": c.id,
            "name": c.name,
            "bvid": c.bvid,
            "coverUrl": c.cover_url,
            "durationMinutes": c.duration_minutes,
            "source": CourseSource(c.source).api,
            "playUrl": c.play_url,
            "subjects": [
                {
                    "id": lk.subject_id,
                    "name": subject_names.get(lk.subject_id, "—"),
                    "isPrimary": lk.is_primary == 1,
                }
                for lk in links.get(c.id, [])
            ],
            "createdAt": to_shanghai(c.created_at),
            "routeRefCount": ref_counts.get(c.id, 0),
        }
        for c in rows
    ]

    # 统计卡口径：全库有效课程（不受筛选影响，同原型）；关联学科数不含「其他学科」
    agg = (
        await db.execute(
            select(func.count(Course.id), func.coalesce(func.sum(Course.duration_minutes), 0))
            .where(Course.deleted_at.is_(None))
        )
    ).one()
    other = await _other_subject(db)
    linked_stmt = (
        select(func.count(func.distinct(CourseSubject.subject_id)))
        .join(Course, Course.id == CourseSubject.course_id)
        .where(Course.deleted_at.is_(None))
    )
    if other is not None:
        linked_stmt = linked_stmt.where(CourseSubject.subject_id != other.id)
    linked_count = (await db.execute(linked_stmt)).scalar() or 0

    return {
        "cards": {
            "total": agg[0],
            "totalHours": round(float(agg[1] or 0) / 60, 1),  # SUM 返回 Decimal，转 float 保证可序列化
            "linkedSubjectCount": linked_count,
        },
        "list": items,
        "total": total,
        "pageNum": q.pageNum,
        "pageSize": q.pageSize,
    }


async def create_course(
    db: AsyncSession, ctx: AdminContext, payload: CourseCreate, ip: str
) -> dict:
    await _validate_course_subjects(db, payload.subjectIds)
    await _check_bvid(db, payload.bvid)

    course = Course(
        name=payload.name,
        bvid=payload.bvid,
        cover_url=payload.coverUrl,
        duration_minutes=payload.durationMinutes,
        source=int(CourseSource.from_api(payload.source)),
        play_url=payload.playUrl,
        sort_seq=await _next_manual_sort_seq(db),  # 非导入：最新在前（S5）
    )
    db.add(course)
    await db.flush()
    await _set_course_subjects(db, course.id, payload.subjectIds)

    await record_operation(
        db,
        action_type=OperationActionType.CREATE,
        action_desc="新增课程",
        target=f"课程「{payload.name}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"id": course.id}


async def _require_course(db: AsyncSession, course_id: int) -> Course:
    course = (
        await db.execute(select(Course).where(Course.id == course_id, Course.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if course is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "课程不存在", http_status=404)
    return course


async def update_course(
    db: AsyncSession, ctx: AdminContext, course_id: int, payload: CourseUpdate, ip: str
) -> dict:
    course = await _require_course(db, course_id)
    await _validate_course_subjects(db, payload.subjectIds)
    await _check_bvid(db, payload.bvid, exclude_id=course_id)

    course.name = payload.name
    course.bvid = payload.bvid
    course.cover_url = payload.coverUrl
    course.duration_minutes = payload.durationMinutes
    course.source = int(CourseSource.from_api(payload.source))
    course.play_url = payload.playUrl
    await _set_course_subjects(db, course.id, payload.subjectIds)  # 整体替换（03 S2）

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="编辑课程",
        target=f"课程「{payload.name}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def delete_course(
    db: AsyncSession, ctx: AdminContext, course_id: int, ip: str
) -> dict:
    course = await _require_course(db, course_id)
    course.deleted_at = utc_now()  # 逻辑删除；引用它的路线保留引用（恢复可见）

    await record_operation(
        db,
        action_type=OperationActionType.DELETE,
        action_desc="删除课程",
        target=f"课程「{course.name}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def export_courses_xlsx(
    db: AsyncSession, ctx: AdminContext, q: CourseQuery, ip: str
) -> tuple[str, bytes]:
    """导出课程 Excel（04 §4.4 补契约）：按当前筛选，列=导入模板列+创建时间（可导出→修改→重导入）。

    导出行为本身入操作日志（S9 归并「其他」，同日志导出口径）。
    """
    rows = list(
        (
            await db.execute(
                select(Course)
                .where(*_course_filters(q))
                .order_by(Course.sort_seq, Course.id)
                .limit(EXPORT_MAX_ROWS)
            )
        ).scalars()
    )
    course_ids = [c.id for c in rows]
    links: dict[int, list[CourseSubject]] = {}
    subject_names: dict[int, str] = {}
    if course_ids:
        link_rows = list(
            (
                await db.execute(
                    select(CourseSubject)
                    .where(CourseSubject.course_id.in_(course_ids))
                    .order_by(CourseSubject.course_id, CourseSubject.is_primary.desc(), CourseSubject.id)
                )
            ).scalars()
        )
        for lk in link_rows:
            links.setdefault(lk.course_id, []).append(lk)
        subject_names = dict(
            (await db.execute(select(Subject.id, Subject.name).where(Subject.deleted_at.is_(None)))).all()
        )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "课程导出"
    ws.append(["课程名称", "时长（分钟）", "所属学科", "来源", "BV号", "封面", "播放链接", "创建时间"])
    for c in rows:
        ws.append(
            [
                c.name,
                c.duration_minutes,
                # 逗号分隔与导入解析口径一致（中英文逗号均可识别），首个=主学科
                ",".join(subject_names.get(lk.subject_id, "") for lk in links.get(c.id, [])),
                "B站" if c.source == int(CourseSource.BILI) else "其他",
                c.bvid or "",
                c.cover_url or "",
                c.play_url or "",
                to_shanghai(c.created_at) or "",
            ]
        )
    buf = io.BytesIO()
    wb.save(buf)

    await record_operation(
        db,
        action_type=OperationActionType.OTHER,
        action_desc="导出课程",
        target="B站课程库",
        detail=f"导出 {len(rows)} 门",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return "courses.xlsx", buf.getvalue()


# ---------- 批量导入（两段式：preview → confirm） ----------

import io
import json
import re
import secrets

import openpyxl
import xlrd
import redis.asyncio as aioredis


def _cell_str(value) -> str:
    """单元格取值归一为字符串（390 / 390.0 → "390"）。"""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _parse_minutes(raw: str) -> Optional[int]:
    s = raw.strip()
    if re.fullmatch(r"\d+(\.0+)?", s or ""):
        n = int(float(s))
        return n if n >= 1 else None
    return None


def _read_sheet(data: bytes, filename: str) -> list[list[str]]:
    """读取单工作表为字符串二维表；表头=首行。文件级问题抛 BizError PARAM_FILE_INVALID。"""
    if filename.lower().endswith(".xls"):
        book = xlrd.open_workbook(file_contents=data)
        if book.nsheets != 1:
            raise BizError(ErrorCode.PARAM_FILE_INVALID, "仅支持单工作表文件", http_status=400)
        sheet = book.sheet_by_index(0)
        return [[_cell_str(v) for v in sheet.row_values(i)] for i in range(sheet.nrows)]
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
    if len(wb.worksheets) != 1:
        raise BizError(ErrorCode.PARAM_FILE_INVALID, "仅支持单工作表文件", http_status=400)
    return [[_cell_str(v) for v in row] for row in wb.active.iter_rows(values_only=True)]


_REQUIRED_COLS = ("课程名称", "时长（分钟）")
_OPTIONAL_COLS = ("所属学科", "来源", "BV号", "封面", "播放链接")


async def preview_course_import(
    db: AsyncSession, r: aioredis.Redis, data: bytes, filename: str
) -> dict:
    """导入预览（04 §4.4）：任一无效行整份拒绝；解析结果缓存 importToken 供确认。"""
    if len(data) > UPLOAD_EXCEL_MAX_BYTES:
        raise BizError(ErrorCode.PARAM_FILE_INVALID, "文件超过 5MB 限制", http_status=400)

    sheet = _read_sheet(data, filename or "")
    if not sheet:
        raise BizError(ErrorCode.PARAM_FILE_INVALID, "文件内容为空", http_status=400)

    header = [_cell_str(h) for h in sheet[0]]
    col_index = {name: header.index(name) for name in _REQUIRED_COLS + _OPTIONAL_COLS if name in header}
    missing = [name for name in _REQUIRED_COLS if name not in col_index]
    if missing:
        return _import_rejected(0, f"缺少必需列：{'、'.join(missing)}")

    data_rows = sheet[1:]
    if not data_rows:
        return _import_rejected(0, "文件无数据行")
    if len(data_rows) > 2000:
        return _import_rejected(0, "超过单次 2000 行上限")

    other = await _other_subject(db)
    valid_subjects = dict(
        (await db.execute(select(Subject.id, Subject.name).where(Subject.deleted_at.is_(None)))).all()
    )
    name_to_id = {n: i for i, n in valid_subjects.items()}

    def cell(row: list[str], col: str) -> str:
        idx = col_index.get(col)
        return row[idx].strip() if idx is not None and idx < len(row) else ""

    errors: list[dict] = []
    warnings: list[dict] = []
    parsed: list[dict] = []
    seen_bvid: set[str] = set()

    for offset, row in enumerate(data_rows):
        row_no = offset + 2  # Excel 行号（含表头）
        name = cell(row, "课程名称")
        if not name:
            errors.append({"rowNo": row_no, "reason": "课程名称缺失"})
            continue
        if len(name) > 200:
            errors.append({"rowNo": row_no, "reason": "课程名称超过 200 字"})
            continue
        minutes = _parse_minutes(cell(row, "时长（分钟）"))
        if minutes is None:
            errors.append({"rowNo": row_no, "reason": "时长须为正整数（分钟）"})
            continue

        bvid = cell(row, "BV号") or None
        if bvid and len(bvid) > 20:
            errors.append({"rowNo": row_no, "reason": "BV号超过 20 字"})
            continue
        if bvid and bvid in seen_bvid:
            errors.append({"rowNo": row_no, "reason": "文件内 BV号重复"})
            continue
        if bvid:
            seen_bvid.add(bvid)

        source_raw = cell(row, "来源")
        if source_raw in ("", "B站", "bili"):
            source = int(CourseSource.BILI)
        elif source_raw in ("其他", "other"):
            source = int(CourseSource.OTHER)
        else:
            errors.append({"rowNo": row_no, "reason": f"来源值无效「{source_raw}」（B站/其他）"})
            continue

        cover_url = cell(row, "封面") or None
        play_url = cell(row, "播放链接") or None
        if (cover_url and len(cover_url) > 255) or (play_url and len(play_url) > 255):
            errors.append({"rowNo": row_no, "reason": "封面/播放链接超过 255 字"})
            continue

        # 所属学科：空 → 其他学科；无法识别/与「其他学科」混选 → 警告并归入「其他学科」
        segs = [s.strip() for s in re.split(r"[，,]", cell(row, "所属学科")) if s.strip()]
        row_warnings: list[str] = []
        if not segs:
            subject_ids = [other.id] if other else []
        else:
            unknown = [s for s in segs if s not in name_to_id]
            if unknown:
                row_warnings.append(f"所属学科「{'、'.join(unknown)}」无法识别，已归入「其他学科」")
                subject_ids = [other.id] if other else []
            elif OTHER_SUBJECT_NAME in segs and len(segs) > 1:
                row_warnings.append("「其他学科」不可与其他学科同时勾选，已归入「其他学科」")
                subject_ids = [other.id] if other else []
            else:
                subject_ids = [name_to_id[s] for s in segs]
        if not subject_ids:
            errors.append({"rowNo": row_no, "reason": "无有效所属学科且「其他学科」不存在"})
            continue
        for reason in row_warnings:
            warnings.append({"rowNo": row_no, "reason": reason})

        parsed.append(
            {
                "name": name,
                "bvid": bvid,
                "coverUrl": cover_url,
                "durationMinutes": minutes,
                "source": source,
                "playUrl": play_url,
                "subjectIds": subject_ids,
                "subjectNames": "、".join(valid_subjects[i] for i in subject_ids),
                "warning": bool(row_warnings),
            }
        )

    if errors:
        # 任一无效行整份拒绝（04 §4.4）：一行都不写入，仅报错误清单
        return {
            "importToken": "",
            "summary": {
                "totalRows": len(data_rows),
                "newCount": 0,
                "updateCount": 0,
                "warningCount": 0,
                "errorCount": len(errors),
            },
            "errors": errors,
            "warnings": warnings,
            "affectedRoutes": {"courses": 0, "routes": 0},
            "rows": [],
        }

    # 匹配：bvid 优先；无 bvid 按「名称+来源」（04 §4.4 覆盖更新语义）
    result_rows: list[dict] = []
    update_ids: list[int] = []
    for item in parsed:
        match: Optional[Course] = None
        if item["bvid"]:
            match = (
                await db.execute(
                    select(Course).where(Course.bvid == item["bvid"], Course.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
        if match is None:
            match = (
                await db.execute(
                    select(Course)
                    .where(
                        Course.name == item["name"],
                        Course.source == item["source"],
                        Course.deleted_at.is_(None),
                    )
                    .order_by(Course.id)
                )
            ).scalars().first()
        item["matchId"] = match.id if match else None
        if match:
            update_ids.append(match.id)
        item["result"] = "warning" if item["warning"] else ("update" if match else "new")
        result_rows.append(item)

    ref_counts = await _route_ref_counts(db, update_ids)
    summary = {
        "totalRows": len(data_rows),
        "newCount": sum(1 for it in result_rows if it["result"] == "new"),
        "updateCount": sum(1 for it in result_rows if it["result"] == "update"),
        "warningCount": sum(1 for it in result_rows if it["result"] == "warning"),
        "errorCount": 0,
    }

    token = secrets.token_urlsafe(24)
    await r.set(
        _IMPORT_TOKEN_PREFIX + token,
        json.dumps({"rows": parsed}, ensure_ascii=False),
        ex=COURSE_IMPORT_TOKEN_TTL_SECONDS,
    )
    return {
        "importToken": token,
        "summary": summary,
        "errors": [],
        "warnings": warnings,
        "affectedRoutes": {
            "courses": len(ref_counts),
            "routes": sum(ref_counts.values()),
        },
        "rows": [
            {
                "rowNo": i + 2,
                "name": it["name"],
                "durationMinutes": it["durationMinutes"],
                "subjectNames": it["subjectNames"],
                "source": CourseSource(it["source"]).api,
                "result": it["result"],
            }
            for i, it in enumerate(result_rows[:COURSE_IMPORT_PREVIEW_ROWS])
        ],
    }


def _import_rejected(row_no: int, reason: str) -> dict:
    """文件级拒绝（缺列/超限等）。"""
    return {
        "importToken": "",
        "summary": {
            "totalRows": 0,
            "newCount": 0,
            "updateCount": 0,
            "warningCount": 0,
            "errorCount": 1,
        },
        "errors": [{"rowNo": row_no, "reason": reason}],
        "warnings": [],
        "affectedRoutes": {"courses": 0, "routes": 0},
        "rows": [],
    }


async def confirm_course_import(
    db: AsyncSession, r: aioredis.Redis, payload: ImportConfirmRequest, ctx: AdminContext, ip: str
) -> dict:
    """确认导入（04 §4.4）：Excel 为权威数据源，覆盖更新 + 关联学科整体替换。"""
    raw = await r.get(_IMPORT_TOKEN_PREFIX + payload.importToken)
    if not raw:
        raise BizError(
            ErrorCode.PARAM_VALIDATION_FAILED, "importToken 无效或已过期，请重新上传", http_status=400
        )
    await r.delete(_IMPORT_TOKEN_PREFIX + payload.importToken)  # 一次性使用
    rows: list[dict] = json.loads(raw)["rows"]

    created = 0
    updated = 0
    seq = await _next_import_seq(db)  # 批次按 Excel 行序占用升序段位（S5）
    for item in rows:
        match: Optional[Course] = None
        if item["bvid"]:
            match = (
                await db.execute(
                    select(Course).where(Course.bvid == item["bvid"], Course.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
        if match is None:
            match = (
                await db.execute(
                    select(Course)
                    .where(
                        Course.name == item["name"],
                        Course.source == item["source"],
                        Course.deleted_at.is_(None),
                    )
                    .order_by(Course.id)
                )
            ).scalars().first()

        if match is not None:
            # 覆盖更新：全字段按 Excel 写入（空可选列按空值覆盖，不保留库中原值）
            match.name = item["name"]
            match.bvid = item["bvid"]
            match.cover_url = item["coverUrl"]
            match.duration_minutes = item["durationMinutes"]
            match.source = item["source"]
            match.play_url = item["playUrl"]
            match.sort_seq = seq  # 覆盖更新的既有课程按 Excel 行序重排（需求 4.3.2）
            course_id = match.id
            updated += 1
        else:
            course = Course(
                name=item["name"],
                bvid=item["bvid"],
                cover_url=item["coverUrl"],
                duration_minutes=item["durationMinutes"],
                source=item["source"],
                play_url=item["playUrl"],
                sort_seq=seq,
            )
            db.add(course)
            await db.flush()
            course_id = course.id
            created += 1
        seq += 1
        await _set_course_subjects(db, course_id, item["subjectIds"])

    await record_operation(
        db,
        action_type=OperationActionType.CREATE,
        action_desc="批量导入课程",
        target="B站课程库",
        detail=f"新增 {created} 门、更新 {updated} 门",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"created": created, "updated": updated}


def build_import_template() -> bytes:
    """导入模板（04 §4.4 GET /courses/import/template → .xlsx 流）。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["课程名称", "时长（分钟）", "所属学科", "来源", "BV号", "封面", "播放链接"])
    ws.append([
        "大模型应用开发实战：从 Prompt 到 Agent", 390,
        "AI应用与智能体开发,AI大模型开发", "B站", "BV1xK4y1E7qA", "🤖", "https://www.bilibili.com/",
    ])
    ws.append(["面试高频算法题精讲（内部资料）", 90, "其他学科", "其他", "", "📘", ""])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ===================== 学习路线管理（04 §4.7） =====================


async def _route_course_rows(db: AsyncSession, route_ids: list[int]) -> dict[int, list[tuple]]:
    """路线 → [(sort_order, course)]（仅有效课程，随父过滤隐藏口径）；一次查询防 N+1。"""
    if not route_ids:
        return {}
    rows = (
        await db.execute(
            select(RouteItem, Course)
            .join(Course, Course.id == RouteItem.course_id)
            .where(RouteItem.route_id.in_(route_ids), Course.deleted_at.is_(None))
            .order_by(RouteItem.route_id, RouteItem.sort_order, RouteItem.id)
        )
    ).all()
    grouped: dict[int, list[tuple]] = {}
    for item, course in rows:
        grouped.setdefault(item.route_id, []).append((item.sort_order, course))
    return grouped


async def _validate_route_courses(db: AsyncSession, course_ids: list[int]) -> None:
    if len(course_ids) != len(set(course_ids)):
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "课程不可重复", http_status=400)
    if not course_ids:
        return
    count = (
        await db.execute(
            select(func.count(Course.id)).where(
                Course.id.in_(course_ids), Course.deleted_at.is_(None)
            )
        )
    ).scalar() or 0
    if count != len(course_ids):
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "存在无效的课程", http_status=400)


async def _require_route(db: AsyncSession, route_id: int) -> Route:
    route = (
        await db.execute(select(Route).where(Route.id == route_id, Route.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if route is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "路线不存在", http_status=404)
    return route


async def _require_route_subject(db: AsyncSession, subject_id: int) -> Subject:
    subject = (
        await db.execute(
            select(Subject).where(Subject.id == subject_id, Subject.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if subject is None:
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "关联学科不存在", http_status=400)
    return subject


async def list_routes(db: AsyncSession, q: RouteQuery) -> dict:
    """路线卡片列表（分页）。"""
    filters = [Route.deleted_at.is_(None)]
    if q.subjectId:
        filters.append(Route.subject_id == q.subjectId)
    if q.status and q.status != "all":
        filters.append(Route.status == int(EnableStatus.from_api(q.status)))
    if q.keyword:
        filters.append(Route.name.like(f"%{q.keyword.strip()}%"))

    total = (await db.execute(select(func.count(Route.id)).where(*filters))).scalar() or 0
    rows = list(
        (
            await db.execute(
                select(Route)
                .where(*filters)
                .order_by(Route.id.desc())
                .offset(q.offset)
                .limit(q.limit)
            )
        ).scalars()
    )

    route_ids = [r.id for r in rows]
    course_map = await _route_course_rows(db, route_ids)
    subject_names = dict(
        (await db.execute(select(Subject.id, Subject.name).where(Subject.deleted_at.is_(None)))).all()
    )

    items = []
    for r in rows:
        pairs = course_map.get(r.id, [])
        items.append(
            {
                "id": r.id,
                "name": r.name,
                "status": EnableStatus(r.status).api,
                "subjectName": subject_names.get(r.subject_id, "—"),
                "targetEducation": r.target_education,
                "description": r.description,
                "courseCount": len(pairs),
                "totalMinutes": sum(c.duration_minutes for _, c in pairs),
                "coursePreview": [
                    {"name": c.name, "coverUrl": c.cover_url} for _, c in pairs[:4]
                ],
                "createdAt": to_shanghai(r.created_at),
            }
        )
    return {"list": items, "total": total, "pageNum": q.pageNum, "pageSize": q.pageSize}


async def get_route(db: AsyncSession, route_id: int) -> dict:
    """路线详情（课程管理页；预览由前端同数据渲染）。"""
    route = await _require_route(db, route_id)
    subject = await _require_route_subject(db, route.subject_id)
    pairs = (await _route_course_rows(db, [route.id])).get(route.id, [])
    return {
        "id": route.id,
        "name": route.name,
        "status": EnableStatus(route.status).api,
        "subjectId": route.subject_id,
        "subjectName": subject.name,
        "icon": route.icon,
        "targetEducation": route.target_education,
        "description": route.description,
        "courseCount": len(pairs),
        "totalMinutes": sum(c.duration_minutes for _, c in pairs),
        "courses": [
            {
                "id": c.id,
                "bvid": c.bvid,
                "name": c.name,
                "durationMinutes": c.duration_minutes,
                "sortOrder": sort_order,
            }
            for sort_order, c in pairs
        ],
        "createdAt": to_shanghai(route.created_at),
    }


async def create_route(
    db: AsyncSession, ctx: AdminContext, payload: RouteCreate, ip: str
) -> dict:
    subject = await _require_route_subject(db, payload.subjectId)
    await _validate_route_courses(db, payload.courseIds)

    route = Route(
        name=payload.name,
        subject_id=subject.id,
        icon=payload.icon,
        target_education=payload.targetEducation,
        description=payload.description,
        status=int(EnableStatus.from_api(payload.status)),
    )
    db.add(route)
    await db.flush()
    for i, cid in enumerate(payload.courseIds, start=1):
        db.add(RouteItem(route_id=route.id, course_id=cid, sort_order=i))

    await record_operation(
        db,
        action_type=OperationActionType.CREATE,
        action_desc="新建路线",
        target=f"路线「{payload.name}」",
        detail=f"含 {len(payload.courseIds)} 门课程",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"id": route.id}


async def update_route(
    db: AsyncSession, ctx: AdminContext, route_id: int, payload: RouteUpdate, ip: str
) -> dict:
    route = await _require_route(db, route_id)
    subject = await _require_route_subject(db, payload.subjectId)

    route.name = payload.name
    route.subject_id = subject.id
    route.icon = payload.icon
    route.target_education = payload.targetEducation
    route.description = payload.description
    route.status = int(EnableStatus.from_api(payload.status))

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="编辑路线",
        target=f"路线「{payload.name}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def delete_route(
    db: AsyncSession, ctx: AdminContext, route_id: int, ip: str
) -> dict:
    route = await _require_route(db, route_id)
    route.deleted_at = utc_now()  # 逻辑删除；已学课程标记不受影响

    await record_operation(
        db,
        action_type=OperationActionType.DELETE,
        action_desc="删除路线",
        target=f"路线「{route.name}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def add_route_items(
    db: AsyncSession, ctx: AdminContext, route_id: int, payload: RouteItemsAdd, ip: str
) -> dict:
    """从课程库添加课程（已添加的自动忽略，04 §4.7）。"""
    route = await _require_route(db, route_id)
    await _validate_route_courses(db, payload.courseIds)

    existing = {
        row[0]
        for row in (
            await db.execute(select(RouteItem.course_id).where(RouteItem.route_id == route.id))
        ).all()
    }
    max_sort = (
        await db.execute(
            select(func.coalesce(func.max(RouteItem.sort_order), 0)).where(
                RouteItem.route_id == route.id
            )
        )
    ).scalar()
    added = 0
    for cid in payload.courseIds:
        if cid in existing:
            continue
        max_sort += 1
        db.add(RouteItem(route_id=route.id, course_id=cid, sort_order=max_sort))
        added += 1

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="添加路线课程",
        target=f"路线「{route.name}」",
        detail=f"新增 {added} 门",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"affected": added}


async def update_route_items(
    db: AsyncSession, ctx: AdminContext, route_id: int, payload: RouteItemsUpdate, ip: str
) -> dict:
    """课程排序/移除（有序全量，整体替换 sortOrder，03 S2）。"""
    route = await _require_route(db, route_id)
    await _validate_route_courses(db, payload.courseIds)

    from sqlalchemy import delete as sa_delete

    await db.execute(sa_delete(RouteItem).where(RouteItem.route_id == route.id))
    for i, cid in enumerate(payload.courseIds, start=1):
        db.add(RouteItem(route_id=route.id, course_id=cid, sort_order=i))

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="更新路线课程",
        target=f"路线「{route.name}」",
        detail=f"调整后 {len(payload.courseIds)} 门",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}
