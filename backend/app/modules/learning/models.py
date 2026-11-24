"""learning 数据模型（03 §2.3 answer_record/wrong_question/student_course）。

- answer_record / student_course 追加型（无 deleted_at、无更新入口）；
- wrong_question 移除=逻辑删除；level 由 wrong_count 派生不落库；
- 掌握单向不回退（S10）；纠正进度仅错题重做场景计数（Q3）。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, BigInteger, Computed, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class AnswerRecord(Base):
    __tablename__ = "answer_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(BigInteger)  # 逻辑关联 student.id
    question_id: Mapped[int] = mapped_column(BigInteger)  # 逻辑关联 question.id
    scene: Mapped[int] = mapped_column(Integer)  # 1刷题练习 2错题重做
    answer: Mapped[Optional[object]] = mapped_column(JSON)  # 作答快照（03 附录 A）
    is_correct: Mapped[int] = mapped_column(Integer)  # 1对 0错（简答按 AI ≥6 判通过）
    ai_grade: Mapped[Optional[object]] = mapped_column(JSON)  # {score, comment, key_points}
    created_at: Mapped[datetime] = mapped_column(server_default="CURRENT_TIMESTAMP")


class WrongQuestion(Base, TimestampMixin):
    __tablename__ = "wrong_question"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(BigInteger)
    question_id: Mapped[int] = mapped_column(BigInteger)
    wrong_count: Mapped[int] = mapped_column(Integer, default=1)  # 等级派生
    correct_streak: Mapped[int] = mapped_column(Integer, default=0)  # 0~3
    mastery_status: Mapped[int] = mapped_column(Integer, default=0)  # 0待复习 1已掌握
    last_wrong_answer: Mapped[Optional[object]] = mapped_column(JSON)  # 「你的答案」快照
    last_wrong_at: Mapped[datetime] = mapped_column()
    mastered_at: Mapped[Optional[datetime]] = mapped_column()
    deleted_at: Mapped[Optional[datetime]] = mapped_column()
    pair_uk: Mapped[Optional[str]] = mapped_column(
        String(64),
        Computed(
            "IF(deleted_at IS NULL, CONCAT(student_id, '-', question_id), NULL)",
            persisted=False,
        ),
        unique=True,
    )


class StudentCourse(Base):
    __tablename__ = "student_course"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(BigInteger)
    course_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(server_default="CURRENT_TIMESTAMP")
