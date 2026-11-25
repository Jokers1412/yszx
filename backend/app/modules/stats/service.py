"""stats 业务服务（04 §3.2 首页 /home/* + §4.2 数据看板）。

口径（03 §5.2）：
  - Hero：精选面试题=已上架题目数、注册学员=学员有效行、AI面试次数=interview_record 行数
    （三项实时统计），好评率=system_setting.good_rate 静态值；
  - streak=W2：截至今天（今天无作答则截至昨天）向前连续有作答的天数，中断归零；
  - 练习量均为作答题次，按 Asia/Shanghai 日界聚合（CONVERT_TZ 固定偏移，同 students 模块）。
看板口径（04 §4.2）：卡片 4 项实时统计；趋势文案=较上周环比；题目分布=各学科全部
有效题目（S13）；最近活动=operation_log 有效行前 5 条；用户增长按注册日期（沪日界）。
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import EnableStatus, QuestionStatus
from app.common.utils import CN_TZ, app_tz, shanghai_today, to_shanghai, utc_now
from app.modules.accounts.models import Student
from app.modules.content.models import Question, Stage, Subject
from app.modules.interview.models import InterviewRecord
from app.modules.learning.models import AnswerRecord, WrongQuestion
from app.modules.stats.schemas import (
    ActivityItem,
    DashboardCards,
    DashboardResult,
    DashboardTrends,
    DistributionItem,
    GrowthPoint,
    HomeStats,
    HotStage,
    LearnStats,
    ProfileStats,
    UserGrowthResult,
    WeekTrendPoint,
)
from app.modules.system.models import OperationLog, SystemSetting

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


async def learn_stats(db: AsyncSession, student_id: int | None) -> dict:
    """学习统计 + 近 7 日趋势（登录）；admin 身份（Q4）无学习数据返回 0 值。"""
    if student_id is None:
        today = datetime.now(app_tz()).date()
        return LearnStats(
            streak=0,
            accuracy=0.0,
            totalPracticed=0,
            todayDone=0,
            weekTrend=[
                WeekTrendPoint(date=(today - timedelta(days=o)).isoformat(), count=0)
                for o in range(6, -1, -1)
            ],
        ).model_dump()
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


async def profile_stats(db: AsyncSession, student_id: int | None) -> dict:
    """个人学习数据（04 §3.1 GET /profile/stats）；admin 身份（Q4）返回全 0。

    口径（03 §5.2）：practiceCount=作答题次；doneQuestions=去重题目数；
    accuracy=答对÷作答（无作答 0）；wrongCount=错题本有效行；interviewCount=完成场次。
    """
    if student_id is None:
        return ProfileStats(
            practiceCount=0, wrongCount=0, interviewCount=0, doneQuestions=0, accuracy=0.0
        ).model_dump()

    total, correct, done = (
        await db.execute(
            select(
                func.count(AnswerRecord.id),
                func.coalesce(func.sum(AnswerRecord.is_correct), 0),
                func.count(func.distinct(AnswerRecord.question_id)),
            ).where(AnswerRecord.student_id == student_id)
        )
    ).one()
    wrong = (
        await db.execute(
            select(func.count(WrongQuestion.id)).where(
                WrongQuestion.student_id == student_id,
                WrongQuestion.deleted_at.is_(None),
            )
        )
    ).scalar_one()
    interviews = (
        await db.execute(
            select(func.count(InterviewRecord.id)).where(
                InterviewRecord.student_id == student_id,
                InterviewRecord.finished_at.is_not(None),
            )
        )
    ).scalar_one()

    total_n = int(total)
    return ProfileStats(
        practiceCount=total_n,
        wrongCount=int(wrong),
        interviewCount=int(interviews),
        doneQuestions=int(done),
        accuracy=round(float(correct) / total_n * 100, 1) if total_n else 0.0,
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


# ===================== 数据看板（04 §4.2） =====================


def _trend_text(current: int, prev: int) -> str:
    """趋势文案：较上周环比（原型 ↑12% 较上周 / ↓2% 较上周 / — 与上周持平）。"""
    delta = current - prev
    if delta == 0:
        return "— 与上周持平"
    if prev == 0:
        return f"↑ 本周新增 {delta}" if delta > 0 else f"↓ 本周减少 {-delta}"
    pct = round(abs(delta) / prev * 100)
    return f"↑ {pct}% 较上周" if delta > 0 else f"↓ {pct}% 较上周"


async def dashboard(db: AsyncSession) -> dict:
    """看板汇总：卡片+环比趋势文案+题目学科分布（S13）+最近活动。"""
    cutoff = utc_now() - timedelta(days=7)

    async def _count(model, *filters, with_deleted: bool = False) -> tuple[int, int]:
        """(当前总数, 7 天前存量) —— 同一有效行口径。"""
        base = list(filters)
        cur = (
            await db.execute(select(func.count(model.id)).where(*base))
        ).scalar_one()
        prev = (
            await db.execute(
                select(func.count(model.id)).where(*base, model.created_at < cutoff)
            )
        ).scalar_one()
        return int(cur), int(prev)

    sub_now, sub_prev = await _count(Subject, Subject.deleted_at.is_(None))
    q_now, q_prev = await _count(Question, Question.deleted_at.is_(None))
    stu_now, stu_prev = await _count(Student, Student.deleted_at.is_(None))
    iv_now, iv_prev = await _count(InterviewRecord)

    # 题目学科分布：各学科全部有效题目（S13，含 0 题学科）
    dist_rows = (
        await db.execute(
            select(Stage.subject_id, func.count(Question.id))
            .select_from(Question)
            .join(Stage, Stage.id == Question.stage_id)
            .where(
                Question.deleted_at.is_(None),
                Stage.deleted_at.is_(None),
            )
            .group_by(Stage.subject_id)
        )
    ).all()
    dist_map = {int(sid): int(n) for sid, n in dist_rows}
    subjects = (
        await db.execute(
            select(Subject.id, Subject.name)
            .where(Subject.deleted_at.is_(None))
            .order_by(Subject.sort_order, Subject.id)
        )
    ).all()

    # 最近活动：operation_log 有效行前 5 条
    logs = (
        (
            await db.execute(
                select(OperationLog)
                .where(OperationLog.deleted_at.is_(None))
                .order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )

    return DashboardResult(
        cards=DashboardCards(
            subjectCount=sub_now,
            questionCount=q_now,
            registeredUsers=stu_now,
            aiInterviewCount=iv_now,
        ),
        trends=DashboardTrends(
            subject=_trend_text(sub_now, sub_prev),
            question=_trend_text(q_now, q_prev),
            user=_trend_text(stu_now, stu_prev),
            interview=_trend_text(iv_now, iv_prev),
        ),
        questionDistribution=[
            DistributionItem(subjectName=s[1], count=dist_map.get(int(s[0]), 0)).model_dump()
            for s in subjects
        ],
        recentActivities=[
            ActivityItem(
                adminUsername=lg.admin_username,
                action=lg.action_desc,
                detail=lg.detail or lg.target,
                at=to_shanghai(lg.created_at) or "",
            ).model_dump()
            for lg in logs
        ],
    ).model_dump()


async def user_growth(db: AsyncSession, days: int) -> dict:
    """用户增长趋势：按注册日期（Asia/Shanghai 日界）计数，缺日补 0。"""
    start_utc = shanghai_today() - timedelta(days=days - 1)
    rows = (
        await db.execute(
            select(
                func.date(func.convert_tz(Student.created_at, "+00:00", "+08:00")),
                func.count(Student.id),
            )
            .where(Student.deleted_at.is_(None), Student.created_at >= start_utc)
            .group_by(func.date(func.convert_tz(Student.created_at, "+00:00", "+08:00")))
        )
    ).all()
    counts = {str(d): int(n) for d, n in rows}
    today_cn = datetime.now(timezone.utc).astimezone(CN_TZ).date()
    points = [
        GrowthPoint(
            date=(today_cn - timedelta(days=i)).strftime("%Y-%m-%d"),
            count=counts.get((today_cn - timedelta(days=i)).strftime("%Y-%m-%d"), 0),
        ).model_dump()
        for i in range(days - 1, -1, -1)
    ]
    return UserGrowthResult(points=points).model_dump()
