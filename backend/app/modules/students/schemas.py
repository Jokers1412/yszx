"""students 请求/响应模型（04 §4.8 学员管理）。

学员由前台注册产生（需求 4.4：无新增/编辑接口）；手机号完整展示不脱敏；
doneCourses 为数组随详情返回（口径 S17）。
"""
from typing import Optional

from pydantic import BaseModel, Field

from app.common.pagination import PageQuery


class StudentQuery(PageQuery):
    keyword: Optional[str] = Field(default=None, max_length=50, description="昵称/手机号模糊")
    status: Optional[str] = Field(default=None, pattern="^(enabled|disabled)$")


class StudentListItem(BaseModel):
    id: int
    nickname: str
    avatarUrl: Optional[str] = None
    phone: str  # 完整手机号（需求 4.4 ✅）
    registeredAt: str
    studyDays: int  # 累计有作答的去重天数（03 §5.2）
    practiceCount: int  # 作答题次
    interviewCount: int  # 完成的 AI 面试场次
    status: str  # enabled | disabled
    lastLoginAt: Optional[str] = None


class StudentProfile(BaseModel):
    id: int
    nickname: str
    avatarUrl: Optional[str] = None
    status: str
    phone: str
    email: Optional[str] = None
    registeredAt: str
    lastLoginAt: Optional[str] = None


class DoneCourse(BaseModel):
    """已学课程（student_course 关联，口径 S17 数组随详情返回）。"""

    id: int
    name: str
    durationMinutes: int


class StudentStats(BaseModel):
    studyDays: int
    doneCourses: list[DoneCourse]
    practiceCount: int
    accuracy: float  # 百分比，1 位小数（无作答 0）


class InterviewSummary(BaseModel):
    count: int


class StudentDetail(BaseModel):
    profile: StudentProfile
    stats: StudentStats
    interviewSummary: InterviewSummary


class InterviewRecordItem(BaseModel):
    finishedAt: str
    subjectName: str
    difficulty: str  # easy | medium | hard
    questionCount: int
    overallScore: float  # 0~100


class StudentStatusPatch(BaseModel):
    status: str = Field(pattern="^(enabled|disabled)$")


class StudentBatchStatus(BaseModel):
    action: str = Field(pattern="^(enable|disable)$")
    ids: list[int] = Field(min_length=1, max_length=500)


class StudentBatchDelete(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
