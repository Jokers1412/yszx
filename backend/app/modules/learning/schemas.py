"""learning 请求/响应模型（04 §3.3 学习路线部分；练习/错题后续补充）。

命名约定（04 §1.1）：JSON 字段 lowerCamelCase；时间 Asia/Shanghai 字符串。
"""
from typing import Optional

from pydantic import BaseModel, Field


class RouteListQuery(BaseModel):
    """GET /routes 查询参数（04 §3.3：subjectId 必填）。"""

    subjectId: int = Field(ge=1)


class RouteProgress(BaseModel):
    """学习进度（Q1 ✅ 已学完按课程全局标记统计）。"""

    done: int
    total: int
    percent: int  # 0~100 取整（原型口径）


class RouteSubjectCard(BaseModel):
    """学科卡片（D4-24：仅路线数，不展示进度）。"""

    id: int
    name: str
    icon: Optional[str] = None
    routeCount: int  # 启用路线数（含 0 条的弱化卡）


class RouteListItem(BaseModel):
    id: int
    name: str
    icon: Optional[str] = None
    targetEducation: Optional[str] = None
    description: Optional[str] = None
    courseCount: int
    totalMinutes: int
    progress: RouteProgress
    lastStudiedAt: Optional[str] = None  # 该路线课程最近标记时间（默认 Tab「最近学习」）


class RouteCourseItem(BaseModel):
    id: int  # 课程 id
    seq: int  # 学习顺序（1 起）
    name: str
    coverUrl: Optional[str] = None
    bvid: Optional[str] = None
    durationMinutes: int
    playUrl: Optional[str] = None
    completed: bool  # student_course 全局标记（Q1）


class RouteDetail(BaseModel):
    id: int
    name: str
    subjectName: str
    targetEducation: Optional[str] = None
    description: Optional[str] = None
    courseCount: int
    totalMinutes: int
    progress: RouteProgress
    courses: list[RouteCourseItem]
