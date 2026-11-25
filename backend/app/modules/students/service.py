"""students 业务服务（04 §4.8 学员管理已实现）。

口径（03 §5.2 / 需求 4.4）：
  - 手机号完整展示不脱敏；学习天数=累计有作答的去重天数（Asia/Shanghai 日界）；
    正确率=答对数÷作答总数（无作答记 0）；刷题数=作答题次；面试次数=完成场次；
  - doneCourses 为数组随详情返回（口径 S17）；
  - 禁用后 refresh 失效（口径 S18：access 短期仍可用，业务接口校验 status）；
  - 删除为逻辑删除（手机号可重新注册，03 §3.3 生成列）；
  - 导出按当前筛选同步流式 xlsx。
"""
import io

import openpyxl
import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.constants import EXPORT_MAX_ROWS
from app.common.enums import Difficulty, EnableStatus, OperationActionType
from app.common.error_codes import ErrorCode
from app.common.utils import now_ts, to_shanghai, utc_now
from app.core import security
from app.core.audit import record_operation
from app.core.context import AdminContext
from app.core.exceptions import BizError
from app.modules.accounts.models import Student
from app.modules.content.models import Course, Subject
from app.modules.interview.models import InterviewRecord
from app.modules.learning.models import AnswerRecord, StudentCourse


def _status_str(value: int) -> str:
    return EnableStatus(value).api


async def _require_student(db: AsyncSession, student_id: int) -> Student:
    student = (
        await db.execute(
            select(Student).where(Student.id == student_id, Student.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if student is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "学员不存在", http_status=404)
    return student


def _student_filters(q) -> list:
    filters = [Student.deleted_at.is_(None)]
    if q.keyword:
        kw = f"%{q.keyword.strip()}%"
        filters.append(Student.nickname.like(kw) | Student.phone.like(kw))
    if q.status:
        filters.append(Student.status == int(EnableStatus.from_api(q.status)))
    return filters


def _day_count_expr():
    """学习天数：按 Asia/Shanghai 日界去重（03 §5.2，CONVERT_TZ 固定偏移无需时区表）。"""
    return func.count(
        func.distinct(func.date(func.convert_tz(AnswerRecord.created_at, "+00:00", "+08:00")))
    )


async def _study_stats(db: AsyncSession, student_ids: list[int]) -> dict[int, dict]:
    """一次聚合学习天数/刷题数/答对数（防 N+1）。"""
    if not student_ids:
        return {}
    rows = (
        await db.execute(
            select(
                AnswerRecord.student_id,
                _day_count_expr(),
                func.count(AnswerRecord.id),
                func.coalesce(func.sum(AnswerRecord.is_correct), 0),
            )
            .where(AnswerRecord.student_id.in_(student_ids))
            .group_by(AnswerRecord.student_id)
        )
    ).all()
    return {
        sid: {"studyDays": days, "practiceCount": total, "correctCount": int(correct)}
        for sid, days, total, correct in rows
    }


async def _interview_counts(db: AsyncSession, student_ids: list[int]) -> dict[int, int]:
    if not student_ids:
        return {}
    rows = (
        await db.execute(
            select(InterviewRecord.student_id, func.count(InterviewRecord.id))
            .where(
                InterviewRecord.student_id.in_(student_ids),
                InterviewRecord.finished_at.is_not(None),
            )
            .group_by(InterviewRecord.student_id)
        )
    ).all()
    return dict(rows)


async def list_students(db: AsyncSession, q) -> dict:
    """学员列表（分页 + 逐行学习/面试统计）。"""
    total = (await db.execute(select(func.count(Student.id)).where(*_student_filters(q)))).scalar() or 0
    rows = list(
        (
            await db.execute(
                select(Student)
                .where(*_student_filters(q))
                .order_by(Student.id.desc())
                .offset(q.offset)
                .limit(q.limit)
            )
        ).scalars()
    )
    ids = [s.id for s in rows]
    stats = await _study_stats(db, ids)
    interviews = await _interview_counts(db, ids)

    return {
        "list": [
            {
                "id": s.id,
                "nickname": s.nickname,
                "avatarUrl": s.avatar_url,
                "phone": s.phone,  # 完整手机号（需求 4.4 ✅）
                "registeredAt": to_shanghai(s.created_at),
                "studyDays": stats.get(s.id, {}).get("studyDays", 0),
                "practiceCount": stats.get(s.id, {}).get("practiceCount", 0),
                "interviewCount": interviews.get(s.id, 0),
                "status": _status_str(s.status),
                "lastLoginAt": to_shanghai(s.last_login_at),
            }
            for s in rows
        ],
        "total": total,
        "pageNum": q.pageNum,
        "pageSize": q.pageSize,
    }


async def get_student(db: AsyncSession, student_id: int) -> dict:
    """学员详情（资料 + 学习统计含已学课程数组 S17 + 面试汇总）。"""
    student = await _require_student(db, student_id)
    stats = (await _study_stats(db, [student.id])).get(
        student.id, {"studyDays": 0, "practiceCount": 0, "correctCount": 0}
    )
    done_rows = (
        await db.execute(
            select(Course)
            .join(StudentCourse, StudentCourse.course_id == Course.id)
            .where(
                StudentCourse.student_id == student.id,
                Course.deleted_at.is_(None),
            )
            .order_by(StudentCourse.created_at.desc())
        )
    ).scalars()
    done_courses = [
        {"id": c.id, "name": c.name, "durationMinutes": c.duration_minutes} for c in done_rows
    ]
    interview_count = (
        await db.execute(
            select(func.count(InterviewRecord.id)).where(
                InterviewRecord.student_id == student.id,
                InterviewRecord.finished_at.is_not(None),
            )
        )
    ).scalar() or 0

    practice = stats["practiceCount"]
    return {
        "profile": {
            "id": student.id,
            "nickname": student.nickname,
            "avatarUrl": student.avatar_url,
            "status": _status_str(student.status),
            "phone": student.phone,
            "email": student.email,
            "registeredAt": to_shanghai(student.created_at),
            "lastLoginAt": to_shanghai(student.last_login_at),
        },
        "stats": {
            "studyDays": stats["studyDays"],
            "doneCourses": done_courses,
            "practiceCount": practice,
            "accuracy": (
                round(stats["correctCount"] / practice * 100, 1) if practice else 0.0
            ),
        },
        "interviewSummary": {"count": interview_count},
    }


async def list_student_interviews(db: AsyncSession, student_id: int, q) -> dict:
    """学员 AI 面试记录（完成场次，分页）。"""
    await _require_student(db, student_id)
    base = select(InterviewRecord, Subject.name).join(
        Subject, Subject.id == InterviewRecord.subject_id
    ).where(
        InterviewRecord.student_id == student_id,
        InterviewRecord.finished_at.is_not(None),
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        await db.execute(base.order_by(InterviewRecord.finished_at.desc()).offset(q.offset).limit(q.limit))
    ).all()
    return {
        "list": [
            {
                "finishedAt": to_shanghai(record.finished_at),
                "subjectName": subject_name,
                "difficulty": Difficulty(record.difficulty).api,
                "questionCount": record.question_count,
                "overallScore": float(record.overall_score or 0),
            }
            for record, subject_name in rows
        ],
        "total": total,
        "pageNum": q.pageNum,
        "pageSize": q.pageSize,
    }


async def _revoke_student_sessions(r: aioredis.Redis, student_id: int) -> None:
    """口径 S18：禁用/删除后 refresh 失效（access 短期仍可用，业务接口校验 status）。"""
    await r.set(security.user_refresh_epoch_key("portal", str(student_id)), str(now_ts()))


async def patch_student_status(
    db: AsyncSession, r: aioredis.Redis, ctx: AdminContext, student_id: int, payload, ip: str
) -> dict:
    student = await _require_student(db, student_id)
    student.status = int(EnableStatus.from_api(payload.status))
    if payload.status == "disabled":
        await _revoke_student_sessions(r, student.id)
    label = "启用" if payload.status == "enabled" else "禁用"

    await record_operation(
        db,
        action_type=OperationActionType.DISABLE,
        action_desc=f"{label}学员",
        target=f"学员「{student.nickname}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def delete_student(
    db: AsyncSession, r: aioredis.Redis, ctx: AdminContext, student_id: int, ip: str
) -> dict:
    student = await _require_student(db, student_id)
    student.deleted_at = utc_now()  # 逻辑删除；手机号生成列释放，可重新注册
    await _revoke_student_sessions(r, student.id)

    await record_operation(
        db,
        action_type=OperationActionType.DELETE,
        action_desc="删除学员",
        target=f"学员「{student.nickname}」",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"success": True}


async def batch_student_status(
    db: AsyncSession, r: aioredis.Redis, ctx: AdminContext, payload, ip: str
) -> dict:
    rows = list(
        (
            await db.execute(
                select(Student).where(Student.id.in_(payload.ids), Student.deleted_at.is_(None))
            )
        ).scalars()
    )
    status = 1 if payload.action == "enable" else 0
    for student in rows:
        student.status = status
    if payload.action == "disable":
        for student in rows:
            await _revoke_student_sessions(r, student.id)
    label = "启用" if payload.action == "enable" else "禁用"

    await record_operation(
        db,
        action_type=OperationActionType.DISABLE,
        action_desc=f"批量{label}学员",
        target=f"{len(rows)} 名学员",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"affected": len(rows)}


async def batch_delete_students(
    db: AsyncSession, r: aioredis.Redis, ctx: AdminContext, payload, ip: str
) -> dict:
    rows = list(
        (
            await db.execute(
                select(Student).where(Student.id.in_(payload.ids), Student.deleted_at.is_(None))
            )
        ).scalars()
    )
    now = utc_now()
    for student in rows:
        student.deleted_at = now
        await _revoke_student_sessions(r, student.id)

    await record_operation(
        db,
        action_type=OperationActionType.DELETE,
        action_desc="批量删除学员",
        target=f"{len(rows)} 名学员",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return {"affected": len(rows)}


async def export_students_xlsx(db: AsyncSession, ctx: AdminContext, q, ip: str) -> tuple[str, bytes]:
    """导出学员列表（按当前筛选，同步 xlsx 流，需求 4.4）。"""
    rows = list(
        (
            await db.execute(
                select(Student)
                .where(*_student_filters(q))
                .order_by(Student.id.desc())
                .limit(EXPORT_MAX_ROWS)
            )
        ).scalars()
    )
    ids = [s.id for s in rows]
    stats = await _study_stats(db, ids)
    interviews = await _interview_counts(db, ids)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "学员导出"
    ws.append(["昵称", "手机号", "邮箱", "注册时间", "学习天数", "刷题数", "面试次数", "状态", "最后登录"])
    for s in rows:
        st = stats.get(s.id, {})
        ws.append(
            [
                s.nickname,
                s.phone,
                s.email or "",
                to_shanghai(s.created_at) or "",
                st.get("studyDays", 0),
                st.get("practiceCount", 0),
                interviews.get(s.id, 0),
                "已启用" if s.status == 1 else "已禁用",
                to_shanghai(s.last_login_at) or "",
            ]
        )
    buf = io.BytesIO()
    wb.save(buf)

    await record_operation(
        db,
        action_type=OperationActionType.OTHER,
        action_desc="导出学员",
        target="学员列表",
        detail=f"导出 {len(rows)} 名",
        admin_user_id=ctx.admin_id,
        admin_username=ctx.username,
        ip=ip,
    )
    await db.commit()
    return "students.xlsx", buf.getvalue()
