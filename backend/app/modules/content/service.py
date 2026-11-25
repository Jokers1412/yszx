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

from sqlalchemy import Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import (
    COURSE_IMPORT_PREVIEW_ROWS,
    COURSE_IMPORT_TOKEN_TTL_SECONDS,
    EXPORT_MAX_ROWS,
    IMPORT_QUESTION_MAX_ROWS,
    OTHER_SUBJECT_NAME,
    THEME_COLOR_PALETTE,
    UPLOAD_EXCEL_MAX_BYTES,
)
from app.common.enums import (
    CourseSource,
    Difficulty,
    EnableStatus,
    OperationActionType,
    QuestionStatus,
    QuestionType,
)
from app.common.error_codes import ErrorCode
from app.common.utils import to_shanghai, utc_now
from app.core.audit import record_operation
from app.core.context import AdminContext
from app.core.exceptions import BizError
from app.modules.content.models import (
    Course,
    CourseSubject,
    Question,
    QuestionOption,
    Route,
    RouteItem,
    Stage,
    Subject,
)
from app.modules.learning.models import AnswerRecord
from app.modules.system.models import AdminUser
from app.modules.content.schemas import (
    CourseCreate,
    CourseQuery,
    CourseUpdate,
    ImportConfirmRequest,
    PortalSubjectCard,
    PortalSubjectDetail,
    PortalStageItem,
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


# ===================== 题库管理（04 §4.5） =====================

_TYPE_CN = {1: "单选", 2: "多选", 3: "判断", 4: "简答"}
_DIFF_CN = {1: "简单", 2: "中等", 3: "困难"}
_TYPE_FROM_CN = {**{v: k for k, v in _TYPE_CN.items()}, "single": 1, "multiple": 2, "judge": 3, "short": 4}
_DIFF_FROM_CN = {**{v: k for k, v in _DIFF_CN.items()}, "easy": 1, "medium": 2, "hard": 3}
_QUESTION_TOKEN_PREFIX = "question:import:"
_QUESTION_STEM_LIMIT = 80  # 列表题干截断长度


def _stem(text: str, limit: int = _QUESTION_STEM_LIMIT) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _question_visible_filter():
    """题目可见口径（随父过滤隐藏，03 S1）：所属阶段与学科均有效。"""
    return (
        select(Question.id)
        .join(Stage, Stage.id == Question.stage_id)
        .join(Subject, Subject.id == Stage.subject_id)
        .where(
            Question.deleted_at.is_(None),
            Stage.deleted_at.is_(None),
            Subject.deleted_at.is_(None),
        )
    )


def _validate_question_form(payload) -> None:
    """按题型校验必填组合（04 §4.5）：单选/多选→选项；判断→judgeAnswer；简答→参考答案可空。"""
    qtype = QuestionType.from_api(payload.type)
    if qtype in (QuestionType.SINGLE, QuestionType.MULTIPLE):
        opts = payload.options or []
        if not 2 <= len(opts) <= 6:
            raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "选项数量需为 2~6 项", http_status=400)
        keys = [o.key for o in opts]
        if len(keys) != len(set(keys)):
            raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "选项编号不可重复", http_status=400)
        correct = [o for o in opts if o.isCorrect]
        if not correct:
            raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "至少勾选 1 个正确答案", http_status=400)
        if qtype == QuestionType.SINGLE and len(correct) > 1:
            raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "单选题仅可有 1 个正确答案", http_status=400)
    elif qtype == QuestionType.JUDGE and payload.judgeAnswer is None:
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "判断题请设置正确答案", http_status=400)


async def _require_question_stage(db: AsyncSession, stage_id: int) -> Stage:
    stage = (
        await db.execute(
            select(Stage)
            .join(Subject, Subject.id == Stage.subject_id)
            .where(
                Stage.id == stage_id,
                Stage.deleted_at.is_(None),
                Subject.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if stage is None:
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "阶段不存在", http_status=400)
    return stage


async def _replace_question_options(db: AsyncSession, question_id: int, options) -> None:
    """选项整体替换（03 S2 编辑替换）。"""
    from sqlalchemy import delete as sa_delete

    await db.execute(sa_delete(QuestionOption).where(QuestionOption.question_id == question_id))
    for i, opt in enumerate(sorted(options or [], key=lambda o: o.key), start=1):
        db.add(
            QuestionOption(
                question_id=question_id,
                option_key=opt.key,
                content=opt.content,
                is_correct=1 if opt.isCorrect else 0,
                sort_order=i,
            )
        )


async def list_questions(db: AsyncSession, q) -> dict:
    """题目列表（分页；题干截断）。"""
    stmt = (
        select(Question, Stage.name, Subject.name)
        .join(Stage, Stage.id == Question.stage_id)
        .join(Subject, Subject.id == Stage.subject_id)
        .where(
            Question.deleted_at.is_(None),
            Stage.deleted_at.is_(None),
            Subject.deleted_at.is_(None),
        )
    )
    if q.keyword:
        kw = f"%{q.keyword.strip()}%"
        stmt = stmt.where(
            Question.content.like(kw) | Question.tags.cast(Text).like(kw)  # 标签 JSON 模糊
        )
    if q.subjectId:
        stmt = stmt.where(Subject.id == q.subjectId)
    if q.stageId:
        stmt = stmt.where(Stage.id == q.stageId)
    if q.type and q.type != "all":
        stmt = stmt.where(Question.type == int(QuestionType.from_api(q.type)))
    if q.difficulty and q.difficulty != "all":
        stmt = stmt.where(Question.difficulty == int(Difficulty.from_api(q.difficulty)))
    if q.status and q.status != "all":
        stmt = stmt.where(Question.status == int(QuestionStatus.from_api(q.status)))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (
        await db.execute(stmt.order_by(Question.id.desc()).offset(q.offset).limit(q.limit))
    ).all()

    return {
        "list": [
            {
                "id": item.id,
                "content": _stem(item.content),
                "subjectName": subject_name,
                "stageName": stage_name,
                "type": QuestionType(item.type).api,
                "difficulty": Difficulty(item.difficulty).api,
                "status": QuestionStatus(item.status).api,
                "createdAt": to_shanghai(item.created_at),
            }
            for item, stage_name, subject_name in rows
        ],
        "total": total,
        "pageNum": q.pageNum,
        "pageSize": q.pageSize,
    }


async def question_summary(db: AsyncSession) -> dict:
    """统计卡（需求 4.3.3 七卡）：与列表同口径（有效题目，随父过滤）。"""
    visible = _question_visible_filter()
    rows = (
        await db.execute(
            select(Question.type, Question.status, func.count())
            .where(Question.id.in_(visible))
            .group_by(Question.type, Question.status)
        )
    ).all()
    summary = {"total": 0, "onShelf": 0, "pending": 0, "single": 0, "multiple": 0, "judge": 0, "short": 0}
    type_key = {1: "single", 2: "multiple", 3: "judge", 4: "short"}
    for qtype, status, cnt in rows:
        summary["total"] += cnt
        summary[type_key[qtype]] += cnt
        if status == int(QuestionStatus.ON_SHELF):
            summary["onShelf"] += cnt
        elif status == int(QuestionStatus.PENDING):
            summary["pending"] += cnt
    return summary


async def get_question_detail(db: AsyncSession, question_id: int) -> dict:
    row = (
        await db.execute(
            select(Question, Stage.name, Subject.name)
            .join(Stage, Stage.id == Question.stage_id)
            .join(Subject, Subject.id == Stage.subject_id)
            .where(
                Question.id == question_id,
                Question.deleted_at.is_(None),
                Stage.deleted_at.is_(None),
                Subject.deleted_at.is_(None),
            )
        )
    ).one_or_none()
    if row is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "题目不存在", http_status=404)
    item, stage_name, subject_name = row

    options = list(
        (
            await db.execute(
                select(QuestionOption)
                .where(QuestionOption.question_id == item.id)
                .order_by(QuestionOption.sort_order, QuestionOption.id)
            )
        ).scalars()
    )
    answer_agg = (
        await db.execute(
            select(func.count(AnswerRecord.id), func.coalesce(func.sum(AnswerRecord.is_correct), 0))
            .where(AnswerRecord.question_id == item.id)
        )
    ).one()
    answer_count, correct_count = answer_agg[0], int(answer_agg[1] or 0)
    created_by = None
    if item.created_by:
        created_by = (
            await db.execute(
                select(AdminUser.username).where(AdminUser.id == item.created_by)
            )
        ).scalar()

    return {
        "id": item.id,
        "stageId": item.stage_id,
        "subjectName": subject_name,
        "stageName": stage_name,
        "type": QuestionType(item.type).api,
        "difficulty": Difficulty(item.difficulty).api,
        "content": item.content,
        "tags": item.tags or [],
        "analysis": item.analysis,
        "options": [
            {"key": o.option_key, "content": o.content, "isCorrect": o.is_correct == 1} for o in options
        ],
        "judgeAnswer": (
            None if item.judge_answer is None else bool(item.judge_answer)
        ),
        "referenceAnswer": item.reference_answer,
        "status": QuestionStatus(item.status).api,
        "createdAt": to_shanghai(item.created_at),
        "createdBy": created_by,
        "stats": {
            "answerCount": answer_count,
            "correctCount": correct_count,
            "accuracy": round(correct_count / answer_count * 100, 1) if answer_count else 0.0,
        },
    }


async def create_question(db: AsyncSession, ctx: AdminContext, payload, ip: str) -> dict:
    _validate_question_form(payload)
    stage = await _require_question_stage(db, payload.stageId)

    question = Question(
        stage_id=stage.id,
        type=int(QuestionType.from_api(payload.type)),
        difficulty=int(Difficulty.from_api(payload.difficulty)),
        status=int(QuestionStatus.PENDING),  # 新增直入「待审核」
        content=payload.content,
        judge_answer=(
            None if payload.judgeAnswer is None else int(payload.judgeAnswer)
        ),
        reference_answer=payload.referenceAnswer,
        analysis=payload.analysis,
        tags=[t.strip() for t in payload.tags if t.strip()] or None,
        created_by=ctx.admin_id,
    )
    db.add(question)
    await db.flush()
    await _replace_question_options(db, question.id, payload.options)

    await record_operation(
        db,
        action_type=OperationActionType.CREATE,
        action_desc="新增题目",
        target=f"题目 #{question.id}",
        detail=_stem(payload.content, 50),
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"id": question.id}


async def _require_question(db: AsyncSession, question_id: int) -> Question:
    question = (
        await db.execute(
            select(Question).where(Question.id == question_id, Question.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if question is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "题目不存在", http_status=404)
    return question


async def update_question(
    db: AsyncSession, ctx: AdminContext, question_id: int, payload, ip: str
) -> dict:
    question = await _require_question(db, question_id)
    _validate_question_form(payload)
    stage = await _require_question_stage(db, payload.stageId)

    # 全量替换（status 只读不接收）；已驳回题目的状态保持，由「重新提交」回待审核
    question.stage_id = stage.id
    question.type = int(QuestionType.from_api(payload.type))
    question.difficulty = int(Difficulty.from_api(payload.difficulty))
    question.content = payload.content
    question.judge_answer = None if payload.judgeAnswer is None else int(payload.judgeAnswer)
    question.reference_answer = payload.referenceAnswer
    question.analysis = payload.analysis
    question.tags = [t.strip() for t in payload.tags if t.strip()] or None
    await _replace_question_options(db, question.id, payload.options)

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="编辑题目",
        target=f"题目 #{question.id}",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def delete_question(db: AsyncSession, ctx: AdminContext, question_id: int, ip: str) -> dict:
    question = await _require_question(db, question_id)
    question.deleted_at = utc_now()  # 逻辑删除（作答记录保留，统计不失真）

    await record_operation(
        db,
        action_type=OperationActionType.DELETE,
        action_desc="删除题目",
        target=f"题目 #{question.id}",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def review_question(
    db: AsyncSession, ctx: AdminContext, question_id: int, payload, ip: str
) -> dict:
    """审核（04 §4.5）：仅「待审核」可审；pass→已上架、reject→已驳回。"""
    question = await _require_question(db, question_id)
    if question.status != int(QuestionStatus.PENDING):
        raise BizError(ErrorCode.BIZ_STATE_INVALID, "仅待审核题目可审核", http_status=409)
    passed = payload.result == "pass"
    question.status = int(QuestionStatus.ON_SHELF if passed else QuestionStatus.REJECTED)

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc=f"审核题目（{'通过' if passed else '不通过'}）",
        target=f"题目 #{question.id}",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"status": QuestionStatus(question.status).api}


async def submit_question(
    db: AsyncSession, ctx: AdminContext, question_id: int, ip: str
) -> dict:
    """重新提交/上架（口径 S14）：已驳回/已下架 → 待审核。"""
    question = await _require_question(db, question_id)
    if question.status not in (int(QuestionStatus.REJECTED), int(QuestionStatus.OFF_SHELF)):
        raise BizError(ErrorCode.BIZ_STATE_INVALID, "仅已驳回/已下架题目可提交审核", http_status=409)
    question.status = int(QuestionStatus.PENDING)

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="提交审核",
        target=f"题目 #{question.id}",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"status": "pending"}


async def unpublish_question(
    db: AsyncSession, ctx: AdminContext, question_id: int, ip: str
) -> dict:
    """下架：仅已上架可下架。"""
    question = await _require_question(db, question_id)
    if question.status != int(QuestionStatus.ON_SHELF):
        raise BizError(ErrorCode.BIZ_STATE_INVALID, "仅已上架题目可下架", http_status=409)
    question.status = int(QuestionStatus.OFF_SHELF)

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="下架题目",
        target=f"题目 #{question.id}",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"status": "offShelf"}


async def batch_review_questions(
    db: AsyncSession, ctx: AdminContext, payload, ip: str
) -> dict:
    """批量审核：仅「待审核」可审，其余跳过并回传 skipped；pass→已上架、reject→已驳回。"""
    rows = list(
        (
            await db.execute(
                select(Question).where(
                    Question.id.in_(payload.ids), Question.deleted_at.is_(None)
                )
            )
        ).scalars()
    )
    by_id = {q.id: q for q in rows}
    affected = 0
    skipped: list[int] = []
    for qid in payload.ids:
        question = by_id.get(qid)
        if question is None or question.status != int(QuestionStatus.PENDING):
            skipped.append(qid)
            continue
        question.status = int(
            QuestionStatus.ON_SHELF if payload.result == "pass" else QuestionStatus.REJECTED
        )
        affected += 1

    passed = payload.result == "pass"
    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc=f"批量审核（{'通过' if passed else '不通过'}）",
        target=f"{len(payload.ids)} 道题目",
        detail=f"成功 {affected} 道、跳过 {len(skipped)} 道",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"affected": affected, "skipped": skipped}


async def batch_status_questions(
    db: AsyncSession, ctx: AdminContext, payload, ip: str
) -> dict:
    """批量状态（口径 S15）：逐条校验合法性，不合法条目跳过并回传 skipped。"""
    rows = list(
        (
            await db.execute(
                select(Question).where(
                    Question.id.in_(payload.ids), Question.deleted_at.is_(None)
                )
            )
        ).scalars()
    )
    by_id = {q.id: q for q in rows}
    affected = 0
    skipped: list[int] = []
    for qid in payload.ids:
        question = by_id.get(qid)
        if question is None:
            skipped.append(qid)
            continue
        if payload.action == "submit" and question.status in (
            int(QuestionStatus.REJECTED),
            int(QuestionStatus.OFF_SHELF),
        ):
            question.status = int(QuestionStatus.PENDING)
            affected += 1
        elif payload.action == "unpublish" and question.status == int(QuestionStatus.ON_SHELF):
            question.status = int(QuestionStatus.OFF_SHELF)
            affected += 1
        else:
            skipped.append(qid)

    await record_operation(
        db,
        action_type=OperationActionType.UPDATE,
        action_desc="批量上架" if payload.action == "submit" else "批量下架",
        target=f"{len(payload.ids)} 道题目",
        detail=f"成功 {affected} 道、跳过 {len(skipped)} 道",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"affected": affected, "skipped": skipped}


async def batch_delete_questions(
    db: AsyncSession, ctx: AdminContext, payload, ip: str
) -> dict:
    rows = list(
        (
            await db.execute(
                select(Question).where(
                    Question.id.in_(payload.ids), Question.deleted_at.is_(None)
                )
            )
        ).scalars()
    )
    now = utc_now()
    for question in rows:
        question.deleted_at = now

    await record_operation(
        db,
        action_type=OperationActionType.DELETE,
        action_desc="批量删除题目",
        target=f"{len(rows)} 道题目",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"affected": len(rows)}


# ---------- 批量导入（两段式，同 §4.4 口径） ----------

_QUESTION_REQUIRED_COLS = ("学科", "阶段", "题干", "题型", "难度", "正确答案")
_QUESTION_OPTIONAL_COLS = ("选项A", "选项B", "选项C", "选项D", "选项E", "选项F", "解析", "标签")
_QUESTION_TEMPLATE_HEADERS = [
    "学科", "阶段", "题干", "题型", "难度",
    "选项A", "选项B", "选项C", "选项D", "选项E", "选项F",
    "正确答案", "解析", "标签",
]


def _parse_correct_letters(raw: str, valid_keys: set[str], single: bool) -> list[str]:
    letters = [ch.upper() for ch in raw if ch.upper() in "ABCDEF"]
    letters = list(dict.fromkeys(letters))
    if not letters or any(k not in valid_keys for k in letters):
        raise ValueError("正确答案与选项不匹配")
    if single and len(letters) != 1:
        raise ValueError("单选题正确答案须为 1 个选项")
    return letters


async def preview_question_import(
    db: AsyncSession, r: aioredis.Redis, data: bytes, filename: str
) -> dict:
    """导入预览（04 §4.5）：任一无效行整份拒绝；阶段按「学科+阶段」两级定位。"""
    if len(data) > UPLOAD_EXCEL_MAX_BYTES:
        raise BizError(ErrorCode.PARAM_FILE_INVALID, "文件超过 5MB 限制", http_status=400)

    sheet = _read_sheet(data, filename or "")
    if not sheet:
        raise BizError(ErrorCode.PARAM_FILE_INVALID, "文件内容为空", http_status=400)

    header = [_cell_str(h) for h in sheet[0]]
    all_cols = _QUESTION_REQUIRED_COLS + _QUESTION_OPTIONAL_COLS
    col_index = {name: header.index(name) for name in all_cols if name in header}
    missing = [name for name in _QUESTION_REQUIRED_COLS if name not in col_index]
    if missing:
        return _import_rejected(0, f"缺少必需列：{'、'.join(missing)}")

    data_rows = sheet[1:]
    if not data_rows:
        return _import_rejected(0, "文件无数据行")
    if len(data_rows) > IMPORT_QUESTION_MAX_ROWS:
        return _import_rejected(0, f"超过单次 {IMPORT_QUESTION_MAX_ROWS} 题上限")

    # （学科名, 阶段名）→ stage_id（仅有效层级）
    stage_rows = (
        await db.execute(
            select(Stage.id, Stage.name, Subject.name)
            .join(Subject, Subject.id == Stage.subject_id)
            .where(Stage.deleted_at.is_(None), Subject.deleted_at.is_(None))
        )
    ).all()
    stage_map: dict[tuple[str, str], int] = {(sn, stn): sid for sid, stn, sn in stage_rows}

    def cell(row: list[str], col: str) -> str:
        idx = col_index.get(col)
        return row[idx].strip() if idx is not None and idx < len(row) else ""

    errors: list[dict] = []
    parsed: list[dict] = []

    for offset, row in enumerate(data_rows):
        row_no = offset + 2
        subject_name = cell(row, "学科")
        stage_name = cell(row, "阶段")
        stage_id = stage_map.get((subject_name, stage_name))
        if stage_id is None:
            errors.append({"rowNo": row_no, "reason": f"所属学科/阶段不存在「{subject_name} / {stage_name}」"})
            continue

        content = cell(row, "题干")
        if not content:
            errors.append({"rowNo": row_no, "reason": "题干缺失"})
            continue
        if len(content) > 5000:
            errors.append({"rowNo": row_no, "reason": "题干超过 5000 字"})
            continue

        qtype = _TYPE_FROM_CN.get(cell(row, "题型"))
        if qtype is None:
            errors.append({"rowNo": row_no, "reason": f"题型无效「{cell(row, '题型')}」（单选/多选/判断/简答）"})
            continue
        difficulty = _DIFF_FROM_CN.get(cell(row, "难度"))
        if difficulty is None:
            errors.append({"rowNo": row_no, "reason": f"难度无效「{cell(row, '难度')}」（简单/中等/困难）"})
            continue

        analysis = cell(row, "解析") or None
        if analysis and len(analysis) > 5000:
            errors.append({"rowNo": row_no, "reason": "解析超过 5000 字"})
            continue
        tags = [t.strip() for t in re.split(r"[，,、]", cell(row, "标签")) if t.strip()]
        if len(tags) > 10:
            errors.append({"rowNo": row_no, "reason": "标签超过 10 个"})
            continue

        options: list[dict] = []
        judge_answer = None
        reference_answer = None
        try:
            if qtype in (1, 2):  # 单选/多选：选项 A~F + 正确答案字母
                for letter in "ABCDEF":
                    text = cell(row, f"选项{letter}")
                    if text:
                        options.append({"key": letter, "content": text[:500], "isCorrect": False})
                if not 2 <= len(options) <= 6:
                    raise ValueError("选项数量需为 2~6 项")
                letters = _parse_correct_letters(
                    cell(row, "正确答案"), {o["key"] for o in options}, single=(qtype == 1)
                )
                for o in options:
                    o["isCorrect"] = o["key"] in letters
            elif qtype == 3:  # 判断
                ans = cell(row, "正确答案")
                if ans in ("正确", "对", "T", "t", "true", "True"):
                    judge_answer = 1
                elif ans in ("错误", "错", "F", "f", "false", "False"):
                    judge_answer = 0
                else:
                    raise ValueError(f"判断题正确答案无效「{ans}」（正确/错误）")
            else:  # 简答：参考答案可空
                reference_answer = cell(row, "正确答案") or None
                if reference_answer and len(reference_answer) > 5000:
                    raise ValueError("参考答案超过 5000 字")
        except ValueError as exc:
            errors.append({"rowNo": row_no, "reason": str(exc)})
            continue

        parsed.append(
            {
                "stageId": stage_id,
                "type": qtype,
                "difficulty": difficulty,
                "content": content,
                "tags": tags,
                "analysis": analysis,
                "options": options,
                "judgeAnswer": judge_answer,
                "referenceAnswer": reference_answer,
                "subjectName": subject_name,
                "stageName": stage_name,
            }
        )

    if errors:
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
            "warnings": [],
            "rows": [],
        }

    token = secrets.token_urlsafe(24)
    await r.set(
        _QUESTION_TOKEN_PREFIX + token,
        json.dumps({"rows": parsed}, ensure_ascii=False),
        ex=COURSE_IMPORT_TOKEN_TTL_SECONDS,
    )
    return {
        "importToken": token,
        "summary": {
            "totalRows": len(data_rows),
            "newCount": len(parsed),  # 导入即「待审核」，均为新增
            "updateCount": 0,
            "warningCount": 0,
            "errorCount": 0,
        },
        "errors": [],
        "warnings": [],
        "rows": [
            {
                "rowNo": i + 2,
                "content": _stem(it["content"]),
                "subjectName": it["subjectName"],
                "stageName": it["stageName"],
                "type": QuestionType(it["type"]).api,
                "difficulty": Difficulty(it["difficulty"]).api,
            }
            for i, it in enumerate(parsed[:COURSE_IMPORT_PREVIEW_ROWS])
        ],
    }


async def confirm_question_import(
    db: AsyncSession, r: aioredis.Redis, payload, ctx: AdminContext, ip: str
) -> dict:
    """确认导入：逐行入库（状态=待审核，选项随行写入）。"""
    raw = await r.get(_QUESTION_TOKEN_PREFIX + payload.importToken)
    if not raw:
        raise BizError(
            ErrorCode.PARAM_VALIDATION_FAILED, "importToken 无效或已过期，请重新上传", http_status=400
        )
    await r.delete(_QUESTION_TOKEN_PREFIX + payload.importToken)
    rows: list[dict] = json.loads(raw)["rows"]

    created = 0
    for item in rows:
        question = Question(
            stage_id=item["stageId"],
            type=item["type"],
            difficulty=item["difficulty"],
            status=int(QuestionStatus.PENDING),  # 导入即「待审核」
            content=item["content"],
            judge_answer=item["judgeAnswer"],
            reference_answer=item["referenceAnswer"],
            analysis=item["analysis"],
            tags=item["tags"] or None,
            created_by=ctx.admin_id,
        )
        db.add(question)
        await db.flush()
        for i, opt in enumerate(item["options"], start=1):
            db.add(
                QuestionOption(
                    question_id=question.id,
                    option_key=opt["key"],
                    content=opt["content"],
                    is_correct=1 if opt["isCorrect"] else 0,
                    sort_order=i,
                )
            )
        created += 1

    await record_operation(
        db,
        action_type=OperationActionType.CREATE,
        action_desc="批量导入题目",
        target="题库",
        detail=f"导入 {created} 道（待审核）",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"created": created, "updated": 0}


def build_question_import_template() -> bytes:
    """导入模板：14 列、四种题型各 1 行示例（需求 4.3.3）。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(_QUESTION_TEMPLATE_HEADERS)
    ws.append([
        "AI应用与智能体开发", "大模型基础", "下列关于大语言模型的描述，正确的是？", "单选", "简单",
        "LLM 只能处理英文文本", "LLM 通过海量文本预训练学习语言规律", "LLM 参数量越小效果越好", "LLM 无需微调即可用于所有场景", "", "",
        "B", "大语言模型通过海量文本预训练学习语言规律。", "大模型,基础概念",
    ])
    ws.append([
        "AI应用与智能体开发", "Agent 开发", "以下哪些属于 AI Agent 的核心组成部分？", "多选", "中等",
        "规划（Planning）", "记忆（Memory）", "工具使用（Tool Use）", "硬盘分区", "", "",
        "ABC", "Agent 由规划、记忆、工具使用与大模型核心组成。", "Agent",
    ])
    ws.append([
        "AI应用与智能体开发", "大模型基础", "一个汉字一定只对应一个 Token。", "判断", "简单",
        "", "", "", "", "", "",
        "错误", "Token 切分取决于分词器与语料。", "Token",
    ])
    ws.append([
        "AI应用与智能体开发", "项目实战", "请简述 RAG 的原理，并说明它解决了大模型的哪些问题。", "简答", "困难",
        "", "", "", "", "", "",
        "RAG 在生成前先检索外部知识库，将片段注入 Prompt 再生成答案。", "RAG 将检索与生成结合，缓解幻觉与知识过时。", "RAG",
    ])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def export_questions_xlsx(
    db: AsyncSession, ctx: AdminContext, q, ip: str
) -> tuple[str, bytes, bool]:
    """导出题目（04 §4.5）：14 列与导入表头一致、可回灌；单次 ≤1 万行，超出截断（S16）。"""
    stmt = (
        select(Question, Stage, Subject)
        .join(Stage, Stage.id == Question.stage_id)
        .join(Subject, Subject.id == Stage.subject_id)
        .where(
            Question.deleted_at.is_(None),
            Stage.deleted_at.is_(None),
            Subject.deleted_at.is_(None),
        )
    )
    if q.keyword:
        kw = f"%{q.keyword.strip()}%"
        stmt = stmt.where(Question.content.like(kw) | Question.tags.cast(Text).like(kw))
    if q.subjectId:
        stmt = stmt.where(Subject.id == q.subjectId)
    if q.stageId:
        stmt = stmt.where(Stage.id == q.stageId)
    if q.type and q.type != "all":
        stmt = stmt.where(Question.type == int(QuestionType.from_api(q.type)))
    if q.difficulty and q.difficulty != "all":
        stmt = stmt.where(Question.difficulty == int(Difficulty.from_api(q.difficulty)))
    if q.status and q.status != "all":
        stmt = stmt.where(Question.status == int(QuestionStatus.from_api(q.status)))

    matched = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar() or 0
    rows = (await db.execute(stmt.order_by(Question.id))).all()[:EXPORT_MAX_ROWS]
    truncated = matched > EXPORT_MAX_ROWS

    question_ids = [item.id for item, _, _ in rows]
    opt_map: dict[int, list[QuestionOption]] = {}
    if question_ids:
        for opt in (
            await db.execute(
                select(QuestionOption)
                .where(QuestionOption.question_id.in_(question_ids))
                .order_by(QuestionOption.question_id, QuestionOption.sort_order, QuestionOption.id)
            )
        ).scalars():
            opt_map.setdefault(opt.question_id, []).append(opt)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "题库导出"
    ws.append(_QUESTION_TEMPLATE_HEADERS)
    for item, stage, subject in rows:
        options = opt_map.get(item.id, [])
        opt_cells = [""] * 6
        correct_letters = ""
        for i, opt in enumerate(options[:6]):
            opt_cells[i] = opt.content
            if opt.is_correct == 1:
                correct_letters += opt.option_key
        if item.type == int(QuestionType.JUDGE):
            correct_letters = "正确" if item.judge_answer == 1 else "错误"
        elif item.type == int(QuestionType.SHORT):
            correct_letters = item.reference_answer or ""
        ws.append(
            [
                subject.name,
                stage.name,
                item.content,
                _TYPE_CN[item.type],
                _DIFF_CN[item.difficulty],
                *opt_cells,
                correct_letters,
                item.analysis or "",
                ",".join(item.tags or []),
            ]
        )
    buf = io.BytesIO()
    wb.save(buf)

    await record_operation(
        db,
        action_type=OperationActionType.OTHER,
        action_desc="导出题目",
        target="题库",
        detail=f"导出 {len(rows)} 道" + ("（已截断）" if truncated else ""),
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return "questions.xlsx", buf.getvalue(), truncated


# ===================== 学员端 · 题库中心（04 §3.3 #16-17） =====================


async def portal_subjects(db: AsyncSession) -> list[dict]:
    """学科列表（题库中心左栏）：仅有效学科按 sort_order，含「其他学科」。

    stageCount=启用阶段数（与 /subjects/{id} 的 stages 口径一致）。
    """
    subjects = (
        await db.execute(
            select(Subject.id, Subject.name, Subject.icon, Subject.description, Subject.theme_color)
            .where(Subject.deleted_at.is_(None))
            .order_by(Subject.sort_order, Subject.id)
        )
    ).all()
    stage_counts = dict(
        (
            await db.execute(
                select(Stage.subject_id, func.count(Stage.id))
                .where(Stage.deleted_at.is_(None), Stage.status == int(EnableStatus.ENABLED))
                .group_by(Stage.subject_id)
            )
        ).all()
    )
    return [
        PortalSubjectCard(
            id=int(s[0]),
            name=s[1],
            icon=s[2],
            description=s[3],
            themeColor=s[4],
            stageCount=int(stage_counts.get(s[0], 0)),
        ).model_dump()
        for s in subjects
    ]


async def portal_subject_detail(db: AsyncSession, subject_id: int) -> dict:
    """学科信息头 + 阶段列表：仅启用阶段；questionCount 限已上架题目。"""
    subject = (
        await db.execute(
            select(Subject).where(Subject.id == subject_id, Subject.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if subject is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "学科不存在", http_status=404)

    stages = (
        await db.execute(
            select(Stage)
            .where(
                Stage.subject_id == subject_id,
                Stage.deleted_at.is_(None),
                Stage.status == int(EnableStatus.ENABLED),
            )
            .order_by(Stage.sort_order, Stage.id)
        )
    ).scalars().all()
    counts: dict[int, int] = {}
    if stages:
        counts = {
            int(r[0]): int(r[1])
            for r in (
                await db.execute(
                    select(Question.stage_id, func.count(Question.id))
                    .where(
                        Question.stage_id.in_([s.id for s in stages]),
                        Question.deleted_at.is_(None),
                        Question.status == int(QuestionStatus.ON_SHELF),
                    )
                    .group_by(Question.stage_id)
                )
            ).all()
        }
    return PortalSubjectDetail(
        id=subject.id,
        name=subject.name,
        icon=subject.icon,
        description=subject.description,
        stageCount=len(stages),
        stages=[
            PortalStageItem(
                id=s.id, name=s.name, icon=s.icon, questionCount=counts.get(s.id, 0)
            ).model_dump()
            for s in stages
        ],
    ).model_dump()
