"""content 数据模型（03 §2.2 subject/stage/question/question_option/
course/course_subject/route/route_item）。

- question_option / course_subject / route_item 为「编辑替换」类（无 deleted_at）；
- question 状态流转：新增→待审核→已上架/已驳回（03 §4）；
- course.bvid 选填全库唯一（活动行唯一生成列，NULL 不校验）。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, BigInteger, Computed, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class Subject(Base, TimestampMixin):
    __tablename__ = "subject"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))
    icon: Mapped[str] = mapped_column(String(10))  # Emoji
    description: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    theme_color: Mapped[str] = mapped_column(String(20))
    deleted_at: Mapped[Optional[datetime]] = mapped_column()
    name_uk: Mapped[Optional[str]] = mapped_column(
        String(50), Computed("IF(deleted_at IS NULL, name, NULL)", persisted=False),
        unique=True,
    )


class Stage(Base, TimestampMixin):
    __tablename__ = "stage"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(BigInteger)  # 逻辑关联 subject.id
    name: Mapped[str] = mapped_column(String(50))
    icon: Mapped[Optional[str]] = mapped_column(String(10))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)  # 1启用 0禁用
    deleted_at: Mapped[Optional[datetime]] = mapped_column()


class Question(Base, TimestampMixin):
    __tablename__ = "question"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stage_id: Mapped[int] = mapped_column(BigInteger)  # 逻辑关联 stage.id
    type: Mapped[int] = mapped_column(Integer)  # 1单选 2多选 3判断 4简答
    difficulty: Mapped[int] = mapped_column(Integer)  # 1简单 2中等 3困难
    status: Mapped[int] = mapped_column(Integer, default=3)  # 默认待审核
    content: Mapped[str] = mapped_column(Text)
    judge_answer: Mapped[Optional[int]] = mapped_column(Integer)  # 仅 type=3：1对 0错
    reference_answer: Mapped[Optional[str]] = mapped_column(Text)  # 仅 type=4
    analysis: Mapped[Optional[str]] = mapped_column(Text)
    tags: Mapped[Optional[list]] = mapped_column(JSON)  # 标签数组
    created_by: Mapped[Optional[int]] = mapped_column(BigInteger)  # 审计用
    deleted_at: Mapped[Optional[datetime]] = mapped_column()


class QuestionOption(Base):
    __tablename__ = "question_option"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(BigInteger)  # 逻辑关联 question.id
    option_key: Mapped[str] = mapped_column(String(1))  # A-F
    content: Mapped[str] = mapped_column(String(500))
    is_correct: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default="CURRENT_TIMESTAMP")


class Course(Base, TimestampMixin):
    __tablename__ = "course"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    bvid: Mapped[Optional[str]] = mapped_column(String(20))
    cover_url: Mapped[Optional[str]] = mapped_column(String(255))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    source: Mapped[int] = mapped_column(Integer, default=1)  # 1B站 2其他
    play_url: Mapped[Optional[str]] = mapped_column(String(255))
    sort_seq: Mapped[int] = mapped_column(BigInteger, default=0)  # 列表顺序权重（03 §7.2 S5）
    deleted_at: Mapped[Optional[datetime]] = mapped_column()
    bvid_uk: Mapped[Optional[str]] = mapped_column(
        String(20), Computed("IF(deleted_at IS NULL, bvid, NULL)", persisted=False),
        unique=True,
    )


class CourseSubject(Base):
    __tablename__ = "course_subject"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(BigInteger)  # 逻辑关联 course.id
    subject_id: Mapped[int] = mapped_column(BigInteger)  # 逻辑关联 subject.id
    is_primary: Mapped[int] = mapped_column(Integer, default=0)  # 1主学科 0关联
    created_at: Mapped[datetime] = mapped_column(server_default="CURRENT_TIMESTAMP")


class Route(Base, TimestampMixin):
    __tablename__ = "route"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(BigInteger)  # 逻辑关联 subject.id
    name: Mapped[str] = mapped_column(String(100))
    icon: Mapped[Optional[str]] = mapped_column(String(10))
    target_education: Mapped[Optional[str]] = mapped_column(String(50))  # 适合学历
    description: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[int] = mapped_column(Integer, default=1)  # 1启用 0禁用（发布/下线）
    deleted_at: Mapped[Optional[datetime]] = mapped_column()


class RouteItem(Base):
    __tablename__ = "route_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    route_id: Mapped[int] = mapped_column(BigInteger)  # 逻辑关联 route.id
    course_id: Mapped[int] = mapped_column(BigInteger)  # 可跨学科补充
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # =学习顺序
    created_at: Mapped[datetime] = mapped_column(server_default="CURRENT_TIMESTAMP")
