"""learning 业务服务（04 §3.3：学习路线已实现；练习/错题后续补充）。

口径：
  - 路线仅启用（status=1）且未删除，学科删除则随父隐藏（03 S1）；
  - 课程随父过滤（course.deleted_at），进度/时长只计有效课程；
  - 已学进度 = student_course 全局标记（Q1 ✅ 跨路线共用），仅标记不可取消（需求 3.7），
    标记接口幂等（uk_student_course 唯一键兜底）；
  - lastStudiedAt = 该路线课程最近标记时间（默认 Tab「最近学习」）；
  - admin 身份（Q4）无学习数据：进度为 0、标记接口拒绝。
"""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.error_codes import ErrorCode
from app.common.utils import to_shanghai
from app.core.exceptions import BizError
from app.modules.content.models import Course, Route, RouteItem, Subject
from app.modules.learning.models import StudentCourse
from app.modules.learning.schemas import (
    RouteCourseItem,
    RouteDetail,
    RouteListItem,
    RouteProgress,
    RouteSubjectCard,
)


def _progress(done: int, total: int) -> RouteProgress:
    return RouteProgress(done=done, total=total, percent=(round(done / total * 100) if total else 0))


async def route_subjects(db: AsyncSession) -> list[dict]:
    """学科卡片（含无路线学科；routeCount=启用路线数，D4-24 不展示进度）。"""
    subjects = (
        await db.execute(
            select(Subject.id, Subject.name, Subject.icon)
            .where(Subject.deleted_at.is_(None))
            .order_by(Subject.sort_order, Subject.id)
        )
    ).all()
    counts = dict(
        (
            await db.execute(
                select(Route.subject_id, func.count(Route.id))
                .where(Route.deleted_at.is_(None), Route.status == 1)
                .group_by(Route.subject_id)
            )
        ).all()
    )
    return [
        RouteSubjectCard(
            id=int(s[0]), name=s[1], icon=s[2], routeCount=int(counts.get(s[0], 0))
        ).model_dump()
        for s in subjects
    ]


async def list_routes(db: AsyncSession, student_id: int | None, subject_id: int) -> list[dict]:
    """路线列表（含进度/最近学习时间）：仅启用路线。"""
    routes = (
        (
            await db.execute(
                select(Route)
                .where(
                    Route.subject_id == subject_id,
                    Route.deleted_at.is_(None),
                    Route.status == 1,
                )
                .order_by(Route.id)
            )
        )
        .scalars()
        .all()
    )
    if not routes:
        return []
    ids = [r.id for r in routes]

    # 课程聚合：courseCount / totalMinutes（仅有效课程，防 N+1）
    agg = {
        int(r[0]): (int(r[1]), int(r[2]))
        for r in (
            await db.execute(
                select(
                    RouteItem.route_id,
                    func.count(Course.id),
                    func.coalesce(func.sum(Course.duration_minutes), 0),
                )
                .select_from(RouteItem)
                .join(Course, (Course.id == RouteItem.course_id) & (Course.deleted_at.is_(None)))
                .where(RouteItem.route_id.in_(ids))
                .group_by(RouteItem.route_id)
            )
        ).all()
    }

    # 已学标记聚合：done + 最近标记时间（Q1 全局标记）
    marks: dict[int, tuple[int, object]] = {}
    if student_id is not None:
        marks = {
            int(r[0]): (int(r[1]), r[2])
            for r in (
                await db.execute(
                    select(
                        RouteItem.route_id,
                        func.count(func.distinct(StudentCourse.course_id)),
                        func.max(StudentCourse.created_at),
                    )
                    .select_from(RouteItem)
                    .join(
                        StudentCourse,
                        (StudentCourse.course_id == RouteItem.course_id)
                        & (StudentCourse.student_id == student_id),
                    )
                    .join(Course, (Course.id == RouteItem.course_id) & (Course.deleted_at.is_(None)))
                    .where(RouteItem.route_id.in_(ids))
                    .group_by(RouteItem.route_id)
                )
            ).all()
        }

    out = []
    for r in routes:
        total, minutes = agg.get(r.id, (0, 0))
        done, last_at = marks.get(r.id, (0, None))
        out.append(
            RouteListItem(
                id=r.id,
                name=r.name,
                icon=r.icon,
                targetEducation=r.target_education,
                description=r.description,
                courseCount=total,
                totalMinutes=minutes,
                progress=_progress(done, total),
                lastStudiedAt=to_shanghai(last_at) if last_at else None,
            ).model_dump()
        )
    return out


async def route_detail(db: AsyncSession, student_id: int | None, route_id: int) -> dict:
    """路线详情（课程按学习顺序 + 已学标记）。"""
    row = (
        await db.execute(
            select(Route, Subject.name)
            .join(Subject, Subject.id == Route.subject_id)
            .where(
                Route.id == route_id,
                Route.deleted_at.is_(None),
                Route.status == 1,
                Subject.deleted_at.is_(None),
            )
        )
    ).one_or_none()
    if row is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "学习路线不存在或已下线", http_status=404)
    route, subject_name = row

    items = (
        await db.execute(
            select(
                RouteItem.course_id,
                Course.name,
                Course.cover_url,
                Course.bvid,
                Course.duration_minutes,
                Course.play_url,
            )
            .select_from(RouteItem)
            .join(Course, (Course.id == RouteItem.course_id) & (Course.deleted_at.is_(None)))
            .where(RouteItem.route_id == route_id)
            .order_by(RouteItem.sort_order, RouteItem.id)
        )
    ).all()

    completed: set[int] = set()
    if student_id is not None and items:
        completed = set(
            (
                await db.execute(
                    select(StudentCourse.course_id).where(
                        StudentCourse.student_id == student_id,
                        StudentCourse.course_id.in_([int(i[0]) for i in items]),
                    )
                )
            ).scalars().all()
        )

    total = len(items)
    done = sum(1 for i in items if int(i[0]) in completed)
    return RouteDetail(
        id=route.id,
        name=route.name,
        subjectName=subject_name,
        targetEducation=route.target_education,
        description=route.description,
        courseCount=total,
        totalMinutes=int(sum(int(i[4]) for i in items)),
        progress=_progress(done, total),
        courses=[
            RouteCourseItem(
                id=int(i[0]),
                seq=idx + 1,
                name=i[1],
                coverUrl=i[2],
                bvid=i[3],
                durationMinutes=int(i[4]),
                playUrl=i[5],
                completed=int(i[0]) in completed,
            ).model_dump()
            for idx, i in enumerate(items)
        ],
    ).model_dump()


async def complete_course(db: AsyncSession, student_id: int | None, course_id: int) -> dict:
    """标记已学完（幂等；仅标记不可取消，需求 3.7 ✅）。"""
    if student_id is None:
        raise BizError(
            ErrorCode.PARAM_VALIDATION_FAILED, "后台账号无学习数据，请使用学员账号", http_status=400
        )
    course = (
        await db.execute(
            select(Course.id).where(Course.id == course_id, Course.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if course is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "课程不存在或已删除", http_status=404)

    exists = (
        await db.execute(
            select(StudentCourse.id).where(
                StudentCourse.student_id == student_id, StudentCourse.course_id == course_id
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        db.add(StudentCourse(student_id=student_id, course_id=course_id))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()  # 并发重复标记 → 幂等成功
    return {"success": True}
