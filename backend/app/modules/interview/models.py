"""interview 数据模型（03 §2.4 interview_question/interview_record/
interview_record_question/interview_report）。

- interview_question 来源标记（手工/Excel 文件名+行号），无上架下架入口；
- interview_record 无删除入口；每日配额计数在 Redis 不落库；
- interview_record_question 追加型快照（题库变更不影响报告）；
- interview_report 1:1 场次；评分公式 W3：overallScore=逐题均分×10。
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import JSON, BigInteger, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class InterviewQuestion(Base, TimestampMixin):
    __tablename__ = "interview_question"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(BigInteger)  # 归属学科（方向=学科）
    content: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[int] = mapped_column(Integer)  # 1简单 2中等 3困难
    topic: Mapped[Optional[str]] = mapped_column(String(100))  # 主题（NULL=未分类）
    tags: Mapped[Optional[list]] = mapped_column(JSON)
    reference_answer: Mapped[Optional[str]] = mapped_column(Text)
    source_type: Mapped[int] = mapped_column(Integer)  # 1手工录入 2Excel导入
    source_file: Mapped[Optional[str]] = mapped_column(String(255))
    source_row: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[int] = mapped_column(Integer, default=1)  # 1已上架（预留）
    deleted_at: Mapped[Optional[datetime]] = mapped_column()


class InterviewRecord(Base, TimestampMixin):
    __tablename__ = "interview_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(BigInteger)
    subject_id: Mapped[int] = mapped_column(BigInteger)  # 面试方向
    difficulty: Mapped[int] = mapped_column(Integer)
    question_count: Mapped[int] = mapped_column(Integer)  # 3/5/8/10/15
    answered_count: Mapped[int] = mapped_column(Integer, default=0)
    overall_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 1))  # 0~100
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column()
    finished_at: Mapped[Optional[datetime]] = mapped_column()


class InterviewRecordQuestion(Base):
    __tablename__ = "interview_record_question"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    interview_record_id: Mapped[int] = mapped_column(BigInteger)  # 逻辑关联场次
    seq: Mapped[int] = mapped_column(Integer)  # 题号 1..N
    interview_question_id: Mapped[Optional[int]] = mapped_column(BigInteger)  # NULL=AI 补充
    question_text: Mapped[str] = mapped_column(Text)  # 题干快照
    reference_answer: Mapped[Optional[str]] = mapped_column(Text)
    user_answer: Mapped[Optional[str]] = mapped_column(Text)  # 超时未答为 NULL
    timed_out: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 1))  # 0~10
    ai_comment: Mapped[Optional[str]] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(server_default="CURRENT_TIMESTAMP")


class InterviewReport(Base, TimestampMixin):
    __tablename__ = "interview_report"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    interview_record_id: Mapped[int] = mapped_column(BigInteger, unique=True)  # 1:1
    overall_comment: Mapped[Optional[str]] = mapped_column(Text)
    accuracy_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))  # %
    ability_scores: Mapped[object] = mapped_column(JSON)  # 六维能力（键固定，03 附录 A）
    strengths: Mapped[Optional[list]] = mapped_column(JSON)  # 优点列表
    improvements: Mapped[Optional[list]] = mapped_column(JSON)  # [{issue, advice}]
    suggestions: Mapped[Optional[list]] = mapped_column(JSON)  # 改进建议
    coaching: Mapped[Optional[object]] = mapped_column(JSON)  # 能力提升三卡
