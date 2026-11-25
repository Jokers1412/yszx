"""interview 请求/响应模型（04 §4.6 面试题库管理 + §3.4 AI 面试流程）。

主题为自由文本（01 阶段 11 确认 D4-20：无词表下拉/词表外标注，筛选模糊匹配）；
来源记 Excel 文件名 + 数据行序号（A2），手工录入 sourceType=manual。
AI 面试命名约定（04 §1.1）：JSON 字段 lowerCamelCase；时间 Asia/Shanghai 字符串。
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.common.pagination import PageQuery


class InterviewQuestionQuery(PageQuery):
    keyword: Optional[str] = Field(default=None, max_length=200, description="题干模糊")
    subjectId: Optional[int] = Field(default=None, ge=1)
    topic: Optional[str] = Field(default=None, max_length=100, description="主题自由文本模糊")
    difficulty: Optional[str] = Field(default="all", pattern="^(all|easy|medium|hard)$")
    unclassifiedOnly: bool = Field(default=False, description="只看未分类（与 topic 互斥）")


class InterviewQuestionListItem(BaseModel):
    id: int
    content: str  # 题干截断
    subjectName: str
    difficulty: str  # easy | medium | hard
    topic: Optional[str] = None  # NULL=未分类
    tags: list[str]
    sourceType: str  # manual | excel
    sourceFile: Optional[str] = None
    sourceRow: Optional[int] = None


class InterviewQuestionDetail(BaseModel):
    id: int
    subjectId: int
    subjectName: str
    content: str
    referenceAnswer: Optional[str] = None
    topic: Optional[str] = None
    tags: list[str]
    difficulty: str
    sourceType: str
    sourceFile: Optional[str] = None
    sourceRow: Optional[int] = None
    createdAt: str


class InterviewQuestionCreate(BaseModel):
    subjectId: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=5000)
    referenceAnswer: Optional[str] = Field(default=None, max_length=10000, description="可留空")
    topic: Optional[str] = Field(default=None, max_length=100, description="自由文本，留空=未分类")
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    tags: list[str] = Field(default_factory=list, max_length=20)


class InterviewQuestionUpdate(BaseModel):
    """编辑（需求 4.3.4：仅可修改主题与难度；其他字段不接收 → extra=forbid）。"""

    model_config = ConfigDict(extra="forbid")

    topic: Optional[str] = Field(default=None, max_length=100, description="清空=未分类")
    difficulty: str = Field(pattern="^(easy|medium|hard)$")


class InterviewImportPreviewRow(BaseModel):
    rowNo: int  # 数据行序号（1 起，与来源「第 N 行」口径一致）
    content: str  # 题干截断
    subjectName: str
    difficulty: str
    topic: Optional[str] = None


class InterviewImportSubjectCount(BaseModel):
    """涉及学科汇总（需求 4.3.4 导入预览）。"""

    subjectName: str
    count: int


# ===================== AI 面试（04 §3.4 #33-38 + 回放；需求 3.8） =====================


class ConfigMetaSubject(BaseModel):
    id: int
    name: str


class ConfigMetaResult(BaseModel):
    """GET /interviews/config-meta（A3 方向=全部有效学科）。"""

    subjects: list[ConfigMetaSubject]
    difficulties: list[str]  # ["easy","medium","hard"]
    questionCounts: list[int]  # [3,5,8,10,15]
    defaultCount: int
    timeoutSeconds: int  # 固定 300（5 分钟/题）
    todayRemaining: int  # 今日剩余配额（Redis，0 点重置）
    dailyQuota: int


class StartInterviewRequest(BaseModel):
    """POST /interviews 发起面试（发起即计 1 次配额，S1）。"""

    subjectId: int = Field(ge=1)
    difficulty: Literal["easy", "medium", "hard"]
    questionCount: Literal[3, 5, 8, 10, 15]


class InterviewQuestionOut(BaseModel):
    seq: int  # 题号 1..N
    questionText: str  # 题干快照（S11 一次下发全部题干）


class StartInterviewResult(BaseModel):
    recordId: int
    questions: list[InterviewQuestionOut]
    timeoutSeconds: int


class AnswerSubmitRequest(BaseModel):
    """POST /interviews/{id}/answers（空作答须 timedOut，超时自动提交）。"""

    seq: int = Field(ge=1)
    answer: str = Field(max_length=2000)
    timedOut: bool = False

    @model_validator(mode="after")
    def _check_answer(self) -> "AnswerSubmitRequest":
        if not self.answer.strip() and not self.timedOut:
            raise ValueError("空作答须标记 timedOut（超时提交）")
        return self


class AnswerSubmitResult(BaseModel):
    seq: int
    score: float  # 0-10（配色阈值 8/6 前端）
    aiComment: str
    isLast: bool


class FinishRequest(BaseModel):
    """POST /interviews/{id}/finish（graceful=true 表示主动中途结束，意图标记）。

    ⚠️ endRemark 是否返回**以实际作答数为准**（全部答完才有，S21），
    不受 graceful 影响；字段仅用于审计/日志区分结束意图。
    """

    graceful: bool = False


class FinishResult(BaseModel):
    endRemark: Optional[str] = None  # AI 结束语（全部答完场景，一次性展示不落库 S21）
    reportId: int
    overallScore: float


class ComparedToLast(BaseModel):
    """同方向上一场分数差（无历史则省略）。"""

    delta: float
    trend: Literal["up", "down", "flat"]


class ReportQuestionDetail(BaseModel):
    seq: int
    questionText: str
    userAnswer: Optional[str] = None  # 超时未答为 None
    score: Optional[float] = None
    aiComment: Optional[str] = None
    timedOut: bool = False


class ReportResult(BaseModel):
    recordId: int
    subjectId: int  # 增量字段：报告页「再来一次」发起需要
    subjectName: str
    difficulty: str
    finishedAt: str
    overallScore: float  # W3：逐题均分 ×10
    accuracyRate: float  # W3：≥6 分题数占比 ×100
    durationSeconds: int
    answeredCount: int
    questionCount: int
    comparedToLast: Optional[ComparedToLast] = None
    abilityScores: dict[str, float]  # 六维（03 附录 A 固定键）
    strengths: list[str]
    improvements: list[dict[str, str]]  # [{issue, advice}]
    suggestions: list[str]
    coaching: dict[str, str]  # {questions, courses, reinterview}
    questionDetails: list[ReportQuestionDetail]


class RecordListItem(BaseModel):
    id: int
    subjectId: int  # 增量字段：「再来一次」发起需要
    subjectName: str
    difficulty: str
    questionCount: int
    answeredCount: int
    overallScore: Optional[float] = None
    durationSeconds: int
    finishedAt: Optional[str] = None


class RecordStats(BaseModel):
    total: int
    averageScore: float
    maxScore: float
    totalSeconds: int


class RecordListResult(BaseModel):
    stats: RecordStats
    list: list[RecordListItem]
    total: int
    pageNum: int
    pageSize: int


class RecordsQuery(PageQuery):
    """GET /interviews 查询参数。"""


class ReplayMessage(BaseModel):
    seq: int
    role: Literal["ai", "user"]
    content: str
    score: Optional[float] = None
    aiComment: Optional[str] = None
    timedOut: Optional[bool] = None
    at: Optional[str] = None


class ReplayResult(BaseModel):
    """面试回放（S12：逐题问答快照重建对话流；仅本人可看）。"""

    id: int
    subjectName: str
    difficulty: str
    finishedAt: Optional[str] = None
    overallScore: Optional[float] = None
    messages: list[ReplayMessage]
