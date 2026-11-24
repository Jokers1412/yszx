"""stats 业务服务（04 §3.2 首页 /home/*）。

口径（03 §5.2）：
  - Hero：精选面试题=已上架题目数、注册学员=学员有效行、AI面试次数=interview_record 行数
    （三项实时统计），好评率=system_setting.good_rate 静态值；
  - streak=W2：截至今天（今天无作答则截至昨天）向前连续有作答的天数，中断归零；
  - 练习量均为作答题次，按 Asia/Shanghai 日界聚合（CONVERT_TZ 固定偏移，同 students 模块）。
"""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import EnableStatus, QuestionStatus
from app.common.utils import app_tz, utc_now
from app.modules.accounts.models import Student
from app.modules.content.models import Question, Stage, Subject
from app.modules.interview.models import InterviewRecord
from app.modules.learning.models import AnswerRecord
from app.modules.stats.schemas import HomeStats, HotStage, LearnStats, WeekTrendPoint
from app.modules.system.models import SystemSetting

# streak 计算回看上限（连续学习天数按年封顶，足够业务语义）
_STREAK_LOOKBACK_DAYS = 400


def _day_expr():
    """Asia/Shanghai 日界（03 §5.2，CONVERT_TZ 固定偏移无需时区表）。"""
    return func.date(func.convert_tz(AnswerRecord.created_at, "+00:00", "+08:00"))


async def home_stats(db: AsyncSession) -> dict:
    """Hero 平台数据（游客）。"""
    featured = (
        await db.execute(
            select(func.count(Question.id)).where(
                Question.deleted_at.is_(None),
                Question.status == int(QuestionStatus.ON_SHELF),
            )
        )
    ).scalar_one()
    students = (
        await db.execute(select(func.count(Student.id)).where(Student.deleted_at.is_(None)))
    ).scalar_one()
    interviews = (await db.execute(select(func.count(InterviewRecord.id)))).scalar_one()
    good_rate = (
        await db.execute(select(SystemSetting.good_rate).order_by(SystemSetting.id).limit(1))
    ).scalar_one_or_none()
    return HomeStats(
        featuredQuestions=int(featured),
        registeredStudents=int(students),
        aiInterviews=int(interviews),
        goodRate=float(good_rate) if good_rate is not None else 0.0,
    ).model_dump()


async def learn_stats(db: AsyncSession, student_id: int) -> dict:
    """学习统计 + 近 7 日趋势（登录）。

    admin 身份（isAdmin 登录学员端）返回 0 值——待 accounts 登录实现时按 Q4 补充判定。
    """
    total, correct = (
        await db.execute(
            select(
                func.count(AnswerRecord.id),
                func.coalesce(func.sum(AnswerRecord.is_correct), 0),
            ).where(AnswerRecord.student_id == student_id)
        )
    ).one()
    total_n = int(total)
    accuracy = round(float(correct) / total_n * 100, 1) if total_n else 0.0

    today = datetime.now(app_tz()).date()
    day_rows = (
        await db.execute(
            select(_day_expr(), func.count(AnswerRecord.id))
            .where(
                AnswerRecord.student_id == student_id,
                # DB 存 naive UTC（02 口径），比较用同口径时间
                AnswerRecord.created_at >= utc_now() - timedelta(days=_STREAK_LOOKBACK_DAYS),
            )
            .group_by(_day_expr())
            .order_by(_day_expr().desc())
        )
    ).all()
    day_map = {row[0]: int(row[1]) for row in day_rows}

    # streak（W2）：今天无作答则截至昨天，向前连续计数，中断即 0
    cursor = today if today in day_map else today - timedelta(days=1)
    streak = 0
    while cursor in day_map:
        streak += 1
        cursor -= timedelta(days=1)

    week = [
        WeekTrendPoint(
            date=(today - timedelta(days=offset)).isoformat(),
            count=day_map.get(today - timedelta(days=offset), 0),
        )
        for offset in range(6, -1, -1)
    ]
    return LearnStats(
        streak=streak,
        accuracy=accuracy,
        totalPracticed=total_n,
        todayDone=day_map.get(today, 0),
        weekTrend=week,
    ).model_dump()


async def hot_stages(db: AsyncSession) -> list[dict]:
    """热门阶段（游客）：启用阶段中「有已上架题目」者（原型口径 count>0）。

    按学科/阶段 sort_order 排序，数量上限 12（04 §3.2）。
    """
    rows = (
        await db.execute(
            select(
                Stage.id,
                Stage.name,
                Stage.icon,
                Subject.id,
                Subject.name,
                func.count(Question.id),
            )
            .join(Subject, Subject.id == Stage.subject_id)
            .outerjoin(
                Question,
                (Question.stage_id == Stage.id)
                & (Question.deleted_at.is_(None))
                & (Question.status == int(QuestionStatus.ON_SHELF)),
            )
            .where(
                Stage.deleted_at.is_(None),
                Stage.status == int(EnableStatus.ENABLED),
                Subject.deleted_at.is_(None),
            )
            .group_by(Stage.id, Stage.name, Stage.icon, Subject.id, Subject.name)
            .having(func.count(Question.id) > 0)
            .order_by(Subject.sort_order, Stage.sort_order)
            .limit(12)
        )
    ).all()
    return [
        HotStage(
            id=int(row[0]),
            name=row[1],
            icon=row[2],
            subjectId=int(row[3]),
            subjectName=row[4],
            questionCount=int(row[5]),
        ).model_dump()
        for row in rows
    ]
