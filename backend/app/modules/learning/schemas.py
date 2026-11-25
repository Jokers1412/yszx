"""learning 请求/响应模型（04 §3.3 学习路线/题库/练习部分；错题后续补充）。

命名约定（04 §1.1）：JSON 字段 lowerCamelCase；时间 Asia/Shanghai 字符串。
"""
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator

from app.common.pagination import PageQuery


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


# ===================== 题库中心（04 §3.3 #18-19） =====================


class StageQuestionQuery(PageQuery):
    """GET /stages/{id}/questions 查询参数。"""

    type: Optional[Literal["single", "multiple", "judge", "short"]] = None
    difficulty: Optional[Literal["easy", "medium", "hard"]] = None
    keyword: Optional[str] = Field(default=None, max_length=100, description="题干模糊")


class QuestionListItem(BaseModel):
    id: int
    seq: int  # 结果集序号（1 起，跨页连续，前端「第 N 题」）
    content: str  # 题干（列表不含正确答案，防作弊）
    type: str
    difficulty: str
    stageName: str
    answeredUsers: int  # 去重作答人数
    accuracy: float  # 答对÷作答（无作答 0）
    tags: list[str]
    hasAnalysis: bool


class QuestionListResult(BaseModel):
    list: list[QuestionListItem]
    total: int
    pageNum: int
    pageSize: int


class QuestionOptionOut(BaseModel):
    key: str
    content: str
    isCorrect: bool


class QuestionDetail(BaseModel):
    """题目详情（查看解析：含正确答案与解析，需求 3.4）。"""

    id: int
    content: str
    type: str
    difficulty: str
    tags: list[str]
    options: Optional[list[QuestionOptionOut]] = None  # 仅单选/多选
    judgeAnswer: Optional[bool] = None  # 仅判断
    referenceAnswer: Optional[str] = None  # 仅简答
    analysis: Optional[str] = None
    stageName: str
    answeredUsers: int
    accuracy: float


# ===================== 刷题练习（04 §3.3 #20-21 / 需求 3.5） =====================


class PracticePaperRequest(BaseModel):
    """POST /practice/paper 练习出题（sequential/random 按范围、single 单题）。"""

    mode: Literal["sequential", "random", "single"]
    stageId: Optional[int] = Field(default=None, ge=1, description="sequential/random 按阶段，缺省=全部题目")
    questionId: Optional[int] = Field(default=None, ge=1, description="single 模式目标题目")
    count: int = Field(default=10, ge=1, description="random 题量（默认 10，上限为范围题目总数）")

    @model_validator(mode="after")
    def _check_scope(self) -> "PracticePaperRequest":
        if self.mode == "single" and self.questionId is None:
            raise ValueError("single 模式必须指定 questionId")
        if self.mode != "single" and self.questionId is not None:
            raise ValueError("questionId 仅用于 single 模式")
        return self


class PaperOptionOut(BaseModel):
    """试卷选项（不含 isCorrect，防作弊）。"""

    key: str
    content: str


class PaperQuestionOut(BaseModel):
    id: int
    seq: int  # 卷内序号（1 起，一次下发全部题干）
    content: str
    type: str
    difficulty: str
    options: Optional[list[PaperOptionOut]] = None  # 仅单选/多选


class PracticePaperResult(BaseModel):
    questions: list[PaperQuestionOut]


class PracticeAnswerRequest(BaseModel):
    """POST /practice/answers 提交作答（单/多选=选项键数组、判断=bool、简答=文本）。"""

    questionId: int = Field(ge=1)
    scene: Literal["practice", "wrongReview"]
    answer: Union[list[str], bool, str]  # 形态按题型在 service 校验


class AiGradeOut(BaseModel):
    """简答 AI 批改结果（DB ai_grade 的 API 形态，key_points → keyPoints）。"""

    score: int
    comment: str
    keyPoints: list[str]


class ObjectiveGradeResult(BaseModel):
    """客观题判分响应。"""

    isCorrect: bool
    correctAnswer: Union[list[str], bool]  # 与作答同形态（选项键数组 / bool）
    analysis: Optional[str] = None


class ShortGradeResult(BaseModel):
    """简答批改响应（≥6 分通过，02 D10）。"""

    isCorrect: bool
    aiGrade: AiGradeOut
    referenceAnswer: Optional[str] = None
