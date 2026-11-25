"""learning 业务服务（04 §3.3：学习路线/题库/练习已实现；错题后续补充）。

口径：
  - 路线仅启用（status=1）且未删除，学科删除则随父隐藏（03 S1）；
  - 课程随父过滤（course.deleted_at），进度/时长只计有效课程；
  - 已学进度 = student_course 全局标记（Q1 ✅ 跨路线共用），仅标记不可取消（需求 3.7），
    标记接口幂等（uk_student_course 唯一键兜底）；
  - lastStudiedAt = 该路线课程最近标记时间（默认 Tab「最近学习」）；
  - admin 身份（Q4）无学习数据：进度为 0、标记/练习接口拒绝。
练习口径（04 §3.3 #20-21）：出题一次下发全部题干且不含答案（防作弊）；客观题服务端即时
判分、简答走 AI 批改（S2 失败 503 不落记录可重试）；每次提交落一条 answer_record
（03 §5.2 统计唯一数据源）；答错自动归集错题本（Q3 仅重做场景计纠正进度、S8 复活、S10 不回退）。
"""
import random

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import (
    AnswerScene,
    Difficulty,
    EnableStatus,
    MasteryStatus,
    QuestionStatus,
    QuestionType,
)
from app.common.error_codes import ErrorCode
from app.common.utils import to_shanghai, utc_now
from app.core.exceptions import BizError
from app.modules.ai import service as ai_service
from app.modules.content.models import Course, Question, QuestionOption, Route, RouteItem, Stage, Subject
from app.modules.learning.models import AnswerRecord, StudentCourse, WrongQuestion
from app.modules.learning.schemas import (
    AiGradeOut,
    ObjectiveGradeResult,
    PaperOptionOut,
    PaperQuestionOut,
    PracticeAnswerRequest,
    PracticePaperRequest,
    PracticePaperResult,
    QuestionDetail,
    QuestionListItem,
    QuestionListResult,
    QuestionOptionOut,
    RouteCourseItem,
    RouteDetail,
    RouteListItem,
    RouteProgress,
    RouteSubjectCard,
    ShortGradeResult,
    StageQuestionQuery,
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


# ===================== 题库中心（04 §3.3 #18-19 / 需求 3.4） =====================
# 口径：仅已上架题目；列表不含正确答案（防作弊），详情才给解析；
# answeredUsers=去重作答人数、accuracy=答对÷作答（03 §5.2，全局统计非个人）。


async def _question_stats(db: AsyncSession, question_ids: list[int]) -> dict[int, tuple[int, float]]:
    """一次聚合题目作答人数/正确率（防 N+1）。"""
    if not question_ids:
        return {}
    rows = (
        await db.execute(
            select(
                AnswerRecord.question_id,
                func.count(func.distinct(AnswerRecord.student_id)),
                func.count(AnswerRecord.id),
                func.coalesce(func.sum(AnswerRecord.is_correct), 0),
            )
            .where(AnswerRecord.question_id.in_(question_ids))
            .group_by(AnswerRecord.question_id)
        )
    ).all()
    out: dict[int, tuple[int, float]] = {}
    for qid, users, total, correct in rows:
        total_n = int(total)
        out[int(qid)] = (int(users), round(float(correct) / total_n * 100, 1) if total_n else 0.0)
    return out


async def stage_questions(db: AsyncSession, stage_id: int, q: StageQuestionQuery) -> dict:
    """阶段题目列表（筛选/分页，题库顺序=id 升序）。"""
    stage = (
        await db.execute(
            select(Stage.id).where(
                Stage.id == stage_id,
                Stage.deleted_at.is_(None),
                Stage.status == int(EnableStatus.ENABLED),
            )
        )
    ).scalar_one_or_none()
    if stage is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "阶段不存在或已停用", http_status=404)

    filters = [
        Question.stage_id == stage_id,
        Question.deleted_at.is_(None),
        Question.status == int(QuestionStatus.ON_SHELF),
    ]
    if q.type:
        filters.append(Question.type == int(QuestionType.from_api(q.type)))
    if q.difficulty:
        filters.append(Question.difficulty == int(Difficulty.from_api(q.difficulty)))
    if q.keyword and q.keyword.strip():
        filters.append(Question.content.like(f"%{q.keyword.strip()}%"))

    total = (
        await db.execute(select(func.count(Question.id)).where(*filters))
    ).scalar_one()
    rows = (
        (
            await db.execute(
                select(Question, Stage.name)
                .join(Stage, Stage.id == Question.stage_id)
                .where(*filters)
                .order_by(Question.id)
                .offset((q.pageNum - 1) * q.pageSize)
                .limit(q.pageSize)
            )
        )
        .all()
    )
    stats = await _question_stats(db, [row[0].id for row in rows])
    offset = (q.pageNum - 1) * q.pageSize
    items = []
    for idx, (question, stage_name) in enumerate(rows):
        users, accuracy = stats.get(question.id, (0, 0.0))
        items.append(
            QuestionListItem(
                id=question.id,
                seq=offset + idx + 1,
                content=question.content,
                type=QuestionType(question.type).api,
                difficulty=Difficulty(question.difficulty).api,
                stageName=stage_name,
                answeredUsers=users,
                accuracy=accuracy,
                tags=question.tags or [],
                hasAnalysis=bool(question.analysis),
            ).model_dump()
        )
    return QuestionListResult(
        list=items, total=int(total), pageNum=q.pageNum, pageSize=q.pageSize
    ).model_dump()


async def question_detail(db: AsyncSession, question_id: int) -> dict:
    """题目详情（查看解析：含正确答案+解析，需求 3.4）。"""
    row = (
        await db.execute(
            select(Question, Stage.name)
            .join(Stage, Stage.id == Question.stage_id)
            .where(
                Question.id == question_id,
                Question.deleted_at.is_(None),
                Question.status == int(QuestionStatus.ON_SHELF),
            )
        )
    ).one_or_none()
    if row is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "题目不存在或未上架", http_status=404)
    question, stage_name = row

    options: list[QuestionOptionOut] | None = None
    if int(question.type) in (int(QuestionType.SINGLE), int(QuestionType.MULTIPLE)):
        opt_rows = (
            await db.execute(
                select(QuestionOption.option_key, QuestionOption.content, QuestionOption.is_correct)
                .where(QuestionOption.question_id == question.id)
                .order_by(QuestionOption.sort_order, QuestionOption.option_key)
            )
        ).all()
        options = [
            QuestionOptionOut(key=o[0], content=o[1], isCorrect=bool(o[2])).model_dump()
            for o in opt_rows
        ]

    users, accuracy = (await _question_stats(db, [question.id])).get(question.id, (0, 0.0))
    return QuestionDetail(
        id=question.id,
        content=question.content,
        type=QuestionType(question.type).api,
        difficulty=Difficulty(question.difficulty).api,
        tags=question.tags or [],
        options=options,
        judgeAnswer=bool(question.judge_answer) if int(question.type) == int(QuestionType.JUDGE) else None,
        referenceAnswer=question.reference_answer if int(question.type) == int(QuestionType.SHORT) else None,
        analysis=question.analysis,
        stageName=stage_name,
        answeredUsers=users,
        accuracy=accuracy,
    ).model_dump()


# ===================== 刷题练习（04 §3.3 #20-21 / 需求 3.5） =====================
# 出题一次下发全部题干、不含答案（防作弊）；进度续做为前端本地行为，无服务端会话。


async def create_paper(db: AsyncSession, student_id: int | None, req: PracticePaperRequest) -> dict:
    """练习出题：sequential=题库顺序、random=打乱抽 count 题、single=单题。"""
    if student_id is None:
        raise BizError(
            ErrorCode.PARAM_VALIDATION_FAILED, "后台账号无学习数据，请使用学员账号", http_status=400
        )

    if req.mode == "single":
        rows = (
            (
                await db.execute(
                    select(Question).where(
                        Question.id == req.questionId,
                        Question.deleted_at.is_(None),
                        Question.status == int(QuestionStatus.ON_SHELF),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not rows:
            raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "题目不存在或未上架", http_status=404)
    else:
        filters = [
            Question.deleted_at.is_(None),
            Question.status == int(QuestionStatus.ON_SHELF),
        ]
        if req.stageId is not None:
            stage = (
                await db.execute(
                    select(Stage.id).where(
                        Stage.id == req.stageId,
                        Stage.deleted_at.is_(None),
                        Stage.status == int(EnableStatus.ENABLED),
                    )
                )
            ).scalar_one_or_none()
            if stage is None:
                raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "阶段不存在或已停用", http_status=404)
            filters.append(Question.stage_id == req.stageId)
        rows = (
            (await db.execute(select(Question).where(*filters).order_by(Question.id))).scalars().all()
        )
        if req.mode == "random":
            rows = random.sample(rows, min(req.count, len(rows)))

    questions = await _paper_questions(db, rows) if rows else []
    return PracticePaperResult(questions=questions).model_dump()


async def _paper_questions(db: AsyncSession, rows: list[Question]) -> list[dict]:
    """组卷输出（不含答案字段，防作弊）；选项一次聚合防 N+1。"""
    multi_ids = [
        r.id for r in rows if int(r.type) in (int(QuestionType.SINGLE), int(QuestionType.MULTIPLE))
    ]
    opts_by_q: dict[int, list[PaperOptionOut]] = {}
    if multi_ids:
        opt_rows = (
            await db.execute(
                select(QuestionOption.question_id, QuestionOption.option_key, QuestionOption.content)
                .where(QuestionOption.question_id.in_(multi_ids))
                .order_by(QuestionOption.sort_order, QuestionOption.option_key)
            )
        ).all()
        for qid, key, content in opt_rows:
            opts_by_q.setdefault(int(qid), []).append(PaperOptionOut(key=key, content=content))

    return [
        PaperQuestionOut(
            id=r.id,
            seq=idx + 1,
            content=r.content,
            type=QuestionType(r.type).api,
            difficulty=Difficulty(r.difficulty).api,
            options=opts_by_q.get(r.id),
        ).model_dump()
        for idx, r in enumerate(rows)
    ]


async def submit_answer(db: AsyncSession, student_id: int | None, req: PracticeAnswerRequest) -> dict:
    """提交作答判分：客观题即时判分、简答 AI 批改（S2 失败 503 不落记录）。"""
    if student_id is None:
        raise BizError(
            ErrorCode.PARAM_VALIDATION_FAILED, "后台账号无学习数据，请使用学员账号", http_status=400
        )
    question = (
        (
            await db.execute(
                select(Question).where(
                    Question.id == req.questionId,
                    Question.deleted_at.is_(None),
                    Question.status == int(QuestionStatus.ON_SHELF),
                )
            )
        )
        .scalars()
        .one_or_none()
    )
    if question is None:
        raise BizError(ErrorCode.RESOURCE_NOT_FOUND, "题目不存在或未上架", http_status=404)
    scene = AnswerScene.from_api(req.scene)
    qtype = QuestionType(question.type)

    # —— 校验作答形态并判分（答案快照 = 规整后的作答，03 附录 A）——
    grade: dict | None = None
    if qtype in (QuestionType.SINGLE, QuestionType.MULTIPLE):
        answer = await _validate_option_answer(db, question, qtype, req.answer)
        correct_keys = [
            o[0]
            for o in (
                await db.execute(
                    select(QuestionOption.option_key, QuestionOption.is_correct)
                    .where(
                        QuestionOption.question_id == question.id,
                        QuestionOption.is_correct == 1,
                    )
                    .order_by(QuestionOption.sort_order, QuestionOption.option_key)
                )
            ).all()
        ]
        is_correct = set(answer) == set(correct_keys)
        result: dict = ObjectiveGradeResult(
            isCorrect=is_correct, correctAnswer=correct_keys, analysis=question.analysis
        ).model_dump()
    elif qtype == QuestionType.JUDGE:
        if not isinstance(req.answer, bool):
            raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "判断题答案须为布尔值", http_status=400)
        answer = req.answer
        correct = bool(question.judge_answer)
        is_correct = answer == correct
        result = ObjectiveGradeResult(
            isCorrect=is_correct, correctAnswer=correct, analysis=question.analysis
        ).model_dump()
    else:  # 简答：AI 批改（0-10，≥6 通过 02 D10）
        if not isinstance(req.answer, str):
            raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "简答题答案须为文本", http_status=400)
        answer = req.answer.strip()
        if not answer:
            raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "简答题答案不能为空", http_status=400)
        if len(answer) > 2000:
            raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "简答题答案不能超过 2000 字", http_status=400)
        # S2：AI 失败在落库前抛 503，不产生任何记录
        grade = await ai_service.grade_short_answer(question.content, answer, question.reference_answer)
        is_correct = grade["score"] >= 6
        result = ShortGradeResult(
            isCorrect=is_correct,
            aiGrade=AiGradeOut(
                score=grade["score"], comment=grade["comment"], keyPoints=grade["key_points"]
            ),
            referenceAnswer=question.reference_answer,
        ).model_dump()

    # —— 落记录 + 错题本归集（并发撞 wrong_question 唯一键时重走一次）——
    async def _writes() -> None:
        db.add(
            AnswerRecord(
                student_id=student_id,
                question_id=question.id,
                scene=int(scene),
                answer=answer,
                is_correct=1 if is_correct else 0,
                ai_grade=grade,
            )
        )
        if not is_correct:
            await _upsert_wrong_question(db, student_id, question.id, answer, scene)
        elif scene == AnswerScene.WRONG_REVIEW:
            await _apply_review_correct(db, student_id, question.id)

    try:
        await _writes()
        await db.commit()
    except IntegrityError:
        await db.rollback()
        await _writes()
        await db.commit()
    return result


async def _validate_option_answer(
    db: AsyncSession, question: Question, qtype: QuestionType, answer: object
) -> list[str]:
    """校验单/多选作答（选项键数组），返回去重排序后的键（作答快照）。"""
    if not isinstance(answer, list) or not answer or not all(isinstance(k, str) for k in answer):
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "选择题答案须为选项键数组", http_status=400)
    keys = sorted(dict.fromkeys(answer))
    if qtype == QuestionType.SINGLE and len(keys) != 1:
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "单选题只能选择一个选项", http_status=400)
    valid = set(
        (
            await db.execute(
                select(QuestionOption.option_key).where(QuestionOption.question_id == question.id)
            )
        )
        .scalars()
        .all()
    )
    if not set(keys) <= valid:
        raise BizError(ErrorCode.PARAM_VALIDATION_FAILED, "包含无效的选项键", http_status=400)
    return keys


async def _upsert_wrong_question(
    db: AsyncSession,
    student_id: int,
    question_id: int,
    answer_snapshot: object,
    scene: AnswerScene,
) -> None:
    """答错归集/更新错题本（03 §2.3.2 计数规则）。

    任意场景答错：wrong_count+1、更新最近答错快照；S8 移除后复活续增；
    S10 掌握状态不回退；correct_streak 仅错题重做场景清零（Q3）。
    """
    rows = (
        (
            await db.execute(
                select(WrongQuestion)
                .where(
                    WrongQuestion.student_id == student_id,
                    WrongQuestion.question_id == question_id,
                )
                .order_by(WrongQuestion.id.desc())
            )
        )
        .scalars()
        .all()
    )
    row = next((r for r in rows if r.deleted_at is None), None) or (rows[0] if rows else None)
    now = utc_now()
    if row is None:
        db.add(
            WrongQuestion(
                student_id=student_id,
                question_id=question_id,
                wrong_count=1,
                correct_streak=0,
                mastery_status=int(MasteryStatus.REVIEWING),
                last_wrong_answer=answer_snapshot,
                last_wrong_at=now,
            )
        )
        return
    row.deleted_at = None  # S8 复活（活动行则幂等）
    row.wrong_count += 1
    row.last_wrong_answer = answer_snapshot
    row.last_wrong_at = now
    if scene == AnswerScene.WRONG_REVIEW:
        row.correct_streak = 0


async def _apply_review_correct(db: AsyncSession, student_id: int, question_id: int) -> None:
    """错题重做答对：correct_streak+1，达 3 自动掌握（Q3 ✅ 掌握单向 S10）。"""
    row = (
        (
            await db.execute(
                select(WrongQuestion).where(
                    WrongQuestion.student_id == student_id,
                    WrongQuestion.question_id == question_id,
                    WrongQuestion.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        return  # 重做请求对应错题已移除/不存在，无进度可计
    row.correct_streak += 1
    if row.correct_streak >= 3 and row.mastery_status == int(MasteryStatus.REVIEWING):
        row.mastery_status = int(MasteryStatus.MASTERED)
        row.mastered_at = utc_now()
