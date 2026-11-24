"""学员管理演示数据（开发/演示用，04 §4.8 页面测试数据）。

8 名学员（含 1 名已禁用），配套生成作答记录（学习天数/刷题数/正确率有差异）、
已学课程（student_course）与 AI 面试记录（interview_record），题目/课程/学科
均对应 seed_demo_content / seed_demo_courses 的演示数据。统一初始密码 123456。

幂等：同手机号的有效学员已存在则整组跳过。
运行：cd backend && .venv/Scripts/python.exe scripts/seed_demo_students.py
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core import security  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.modules.accounts.models import Student  # noqa: E402
from app.modules.content.models import Course, Question, Subject  # noqa: E402
from app.modules.interview.models import InterviewRecord  # noqa: E402
from app.modules.learning.models import AnswerRecord, StudentCourse  # noqa: E402

BASE = datetime(2026, 11, 24, 10, 0, 0)  # 演示时间基准（UTC 存储口径）

# (昵称, 手机号, 邮箱, 状态, 学习画像: (作答题次, 覆盖天数, 正确率%), 已学课程数, 面试场次)
DEMO_STUDENTS = [
    ("小北同学", "13800001001", "xiaobei@example.com", 1, (24, 6, 75), 3, 3),
    ("转行小白", "13800001002", "xiaobai@example.com", 1, (8, 2, 38), 1, 1),
    ("算法进阶", "13800001003", "suanfa@example.com", 1, (36, 9, 86), 4, 4),
    ("测试老王", "13800001004", "laowang@example.com", 1, (12, 3, 58), 2, 0),
    ("运维转型", "13800001005", "yunwei@example.com", 1, (18, 4, 66), 2, 2),
    ("设计喵", "13800001006", "miaodesign@example.com", 1, (5, 1, 40), 1, 1),
    ("视频小李", "13800001007", "xiaoli@example.com", 1, (0, 0, 0), 0, 0),
    ("休眠用户", "13800001008", "sleep@example.com", 0, (10, 3, 50), 1, 1),
]


async def main() -> None:
    async with SessionLocal() as db:
        question_ids = list(
            (await db.execute(select(Question.id).where(Question.deleted_at.is_(None)))).scalars()
        )
        courses = list(
            (await db.execute(select(Course).where(Course.deleted_at.is_(None)).order_by(Course.id))).scalars()
        )
        subjects = list(
            (await db.execute(select(Subject).where(Subject.deleted_at.is_(None)).order_by(Subject.id))).scalars()
        )
        if not question_ids or not courses or not subjects:
            print("缺少演示题目/课程/学科，请先运行 seed_demo_content.py / seed_demo_courses.py")
            return

        pwd = security.hash_password("123456")
        created = 0
        for idx, (nick, phone, email, status, profile, done_n, iv_n) in enumerate(DEMO_STUDENTS):
            exists = (
                await db.execute(
                    select(Student.id).where(Student.phone == phone, Student.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            if exists is not None:
                print(f"[跳过] 学员「{nick}」已存在")
                continue

            practice_n, days_n, acc = profile
            student = Student(
                phone=phone,
                password_hash=pwd,
                nickname=nick,
                email=email,
                gender=idx % 3,
                status=status,
                last_login_at=BASE - timedelta(hours=idx * 7 + 3) if practice_n else None,
            )
            db.add(student)
            await db.flush()

            # 作答记录：practice_n 题次分布在 days_n 天内，按正确率铺 is_correct
            for i in range(practice_n):
                day_offset = i % max(days_n, 1)
                correct = 1 if (i + 1) * 100 <= acc * practice_n + 50 else 0
                db.add(
                    AnswerRecord(
                        student_id=student.id,
                        question_id=question_ids[i % len(question_ids)],
                        scene=1,
                        is_correct=correct,
                        created_at=BASE - timedelta(days=day_offset, hours=i % 9),
                    )
                )

            # 已学课程
            for i in range(done_n):
                db.add(StudentCourse(student_id=student.id, course_id=courses[(idx + i) % len(courses)].id))

            # AI 面试记录（完成场次）
            for i in range(iv_n):
                finished = BASE - timedelta(days=i * 3 + idx, hours=2)
                db.add(
                    InterviewRecord(
                        student_id=student.id,
                        subject_id=subjects[(idx + i) % len(subjects)].id,
                        difficulty=(idx + i) % 3 + 1,
                        question_count=[3, 5, 8, 10, 15][(idx + i) % 5],
                        answered_count=[3, 5, 8, 10, 15][(idx + i) % 5],
                        overall_score=round(55 + (idx * 7 + i * 11) % 40 + 0.5, 1),
                        duration_seconds=600 + (idx * 137 + i * 311) % 1200,
                        started_at=finished - timedelta(minutes=25),
                        finished_at=finished,
                    )
                )

            created += 1
            print(f"[新增] {nick}（{phone}，作答 {practice_n} / 已学 {done_n} 门 / 面试 {iv_n} 场）")

        await db.commit()
        print(f"完成：新增 {created} 名学员（其余已存在跳过）")


if __name__ == "__main__":
    asyncio.run(main())
