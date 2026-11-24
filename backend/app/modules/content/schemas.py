"""content 请求/响应模型（04 §4.3 学科管理；§4.4-4.7 课程/题目/路线后续补充）。

命名约定（04 §1.1）：JSON lowerCamelCase；不返回 deletedAt 等内部字段；
status 采用字符串枚举 enabled|disabled（04 附录 C），入库转 1|0。
"""
from typing import Optional

from pydantic import BaseModel, Field

from app.common.pagination import PageQuery


# ---------- 学科管理（04 §4.3）----------

class StageItem(BaseModel):
    id: int
    name: str
    icon: Optional[str] = None
    sortOrder: int
    status: str  # enabled | disabled
    questionCount: int


class SubjectItem(BaseModel):
    id: int
    name: str
    icon: str
    description: str
    sortOrder: int
    themeColor: str
    courseCount: int
    routeCount: int
    questionCount: int
    stages: list[StageItem]


class SubjectCards(BaseModel):
    total: int
    withStages: int
    stageTotal: int
    questionTotal: int


class SubjectListResult(BaseModel):
    cards: SubjectCards
    list: list[SubjectItem]


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50, description="学科名称（活动行唯一）")
    icon: str = Field(min_length=1, max_length=10, description="学科图标 Emoji")
    description: str = Field(min_length=1, max_length=255)
    sortOrder: Optional[int] = Field(
        default=None, ge=0, description="目标位置（1 起越小越靠前；缺省追加末尾）"
    )
    themeColor: str = Field(min_length=1, max_length=20, description="预置色板取值")


class SubjectUpdate(SubjectCreate):
    """编辑学科（全量替换，口径同新增）。"""


class SubjectSort(BaseModel):
    orderedIds: list[int] = Field(min_length=1, description="全量 id，按新顺序")


class StageCreate(BaseModel):
    subjectId: int = Field(ge=1, description="所属学科 id")
    name: str = Field(min_length=1, max_length=50)
    icon: Optional[str] = Field(default=None, max_length=10, description="留空默认 📌")
    sortOrder: Optional[int] = Field(default=None, ge=0, description="目标位置（1 起；缺省追加末尾）")


class StageUpdate(BaseModel):
    """编辑阶段（同新增字段，全量替换）。"""

    subjectId: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=50)
    icon: Optional[str] = Field(default=None, max_length=10)
    sortOrder: Optional[int] = Field(default=None, ge=0)


class StageStatusPatch(BaseModel):
    status: str = Field(pattern="^(enabled|disabled)$", description="enabled|disabled")


class StageSort(BaseModel):
    subjectId: int = Field(ge=1)
    orderedIds: list[int] = Field(min_length=1, description="该学科全量阶段 id，按新顺序")


# ---------- B站课程库（04 §4.4）----------

class CourseQuery(PageQuery):
    keyword: Optional[str] = Field(default=None, max_length=200, description="课程标题模糊")
    subjectId: Optional[int] = Field(default=None, ge=1)
    source: Optional[str] = Field(default="all", pattern="^(all|bili|other)$")


class CourseSubjectRef(BaseModel):
    id: int
    name: str
    isPrimary: bool


class CourseItem(BaseModel):
    id: int
    name: str
    bvid: Optional[str] = None
    coverUrl: Optional[str] = None
    durationMinutes: int
    source: str  # bili | other
    playUrl: Optional[str] = None
    subjects: list[CourseSubjectRef]
    createdAt: str
    routeRefCount: int = 0  # 删除确认提示所需（04 §4.4 DELETE：提示由前端列表数据给出）


class CourseCards(BaseModel):
    total: int
    totalHours: float
    linkedSubjectCount: int


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    bvid: Optional[str] = Field(default=None, max_length=20, description="选填、全库唯一")
    coverUrl: Optional[str] = Field(default=None, max_length=255)
    durationMinutes: int = Field(ge=1, description="时长（分钟）")
    source: str = Field(pattern="^(bili|other)$")
    playUrl: Optional[str] = Field(default=None, max_length=255)
    subjectIds: list[int] = Field(min_length=1, description="第一个=主学科；含「其他学科」时仅可单选")


class CourseUpdate(CourseCreate):
    """编辑课程（全量替换，关联学科整体替换，03 S2）。"""


class ImportSummary(BaseModel):
    totalRows: int
    newCount: int
    updateCount: int
    warningCount: int
    errorCount: int


class ImportIssue(BaseModel):
    rowNo: int  # 0 = 文件级（如缺少必需列）
    reason: str


class ImportAffectedRoutes(BaseModel):
    courses: int  # 被路线引用的受影响课程数
    routes: int  # 引用路线条数合计


class ImportPreviewRow(BaseModel):
    rowNo: int
    name: str
    durationMinutes: int
    subjectNames: str
    source: str  # bili | other
    result: str  # new | update | warning


class ImportPreviewResult(BaseModel):
    importToken: str
    summary: ImportSummary
    errors: list[ImportIssue]
    warnings: list[ImportIssue]
    affectedRoutes: ImportAffectedRoutes
    rows: list[ImportPreviewRow]  # 前 20 行预览


class ImportConfirmRequest(BaseModel):
    importToken: str = Field(min_length=1, max_length=64)


class ImportConfirmResult(BaseModel):
    created: int
    updated: int


# ---------- 学习路线管理（04 §4.7）----------

class RouteQuery(PageQuery):
    subjectId: Optional[int] = Field(default=None, ge=1)
    status: Optional[str] = Field(default="all", pattern="^(all|enabled|disabled)$")
    keyword: Optional[str] = Field(default=None, max_length=100, description="路线名称模糊")


class RouteCoursePreview(BaseModel):
    name: str
    coverUrl: Optional[str] = None


class RouteCard(BaseModel):
    id: int
    name: str
    status: str  # enabled | disabled
    subjectName: str
    targetEducation: Optional[str] = None
    description: Optional[str] = None
    courseCount: int
    totalMinutes: int
    coursePreview: list[RouteCoursePreview]  # 前 4 门
    createdAt: str


class RouteCourseItem(BaseModel):
    id: int
    bvid: Optional[str] = None
    name: str
    durationMinutes: int
    sortOrder: int


class RouteDetail(BaseModel):
    id: int
    name: str
    status: str
    subjectId: int
    subjectName: str
    icon: Optional[str] = None
    targetEducation: Optional[str] = None
    description: Optional[str] = None
    courseCount: int
    totalMinutes: int
    courses: list[RouteCourseItem]
    createdAt: str


class RouteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    subjectId: int = Field(ge=1)
    status: str = Field(pattern="^(enabled|disabled)$")
    icon: Optional[str] = Field(default=None, max_length=10, description="路线图标 Emoji")
    targetEducation: Optional[str] = Field(default=None, max_length=50, description="适合学历")
    description: Optional[str] = Field(default=None, max_length=500)
    courseIds: list[int] = Field(default_factory=list, description="有序课程 id（可空）")


class RouteUpdate(BaseModel):
    """编辑路线（基本信息全量更新，不含课程，04 §4.7）。"""

    name: str = Field(min_length=1, max_length=100)
    subjectId: int = Field(ge=1)
    status: str = Field(pattern="^(enabled|disabled)$")
    icon: Optional[str] = Field(default=None, max_length=10)
    targetEducation: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=500)


class RouteItemsAdd(BaseModel):
    courseIds: list[int] = Field(min_length=1, description="多选添加；已添加的自动忽略")


class RouteItemsUpdate(BaseModel):
    courseIds: list[int] = Field(description="有序全量数组，未含即移除")


# ---------- 题库管理（04 §4.5）----------

class QuestionQuery(PageQuery):
    keyword: Optional[str] = Field(default=None, max_length=200, description="题干/标签模糊")
    subjectId: Optional[int] = Field(default=None, ge=1)
    stageId: Optional[int] = Field(default=None, ge=1)
    type: Optional[str] = Field(default="all", pattern="^(all|single|multiple|judge|short)$")
    difficulty: Optional[str] = Field(default="all", pattern="^(all|easy|medium|hard)$")
    status: Optional[str] = Field(
        default="all", pattern="^(all|onShelf|offShelf|pending|draft|rejected)$"
    )


class QuestionListItem(BaseModel):
    id: int
    content: str  # 题干截断
    subjectName: str
    stageName: str
    type: str  # single | multiple | judge | short
    difficulty: str  # easy | medium | hard
    status: str
    createdAt: str


class QuestionSummary(BaseModel):
    total: int
    onShelf: int
    pending: int
    single: int
    multiple: int
    judge: int
    short: int


class QuestionOptionIn(BaseModel):
    key: str = Field(pattern="^[A-F]$")
    content: str = Field(min_length=1, max_length=500)
    isCorrect: bool


class QuestionCreate(BaseModel):
    stageId: int = Field(ge=1)
    type: str = Field(pattern="^(single|multiple|judge|short)$")
    difficulty: str = Field(pattern="^(easy|medium|hard)$")
    content: str = Field(min_length=1, max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=10, description="≤10 个标签")
    analysis: Optional[str] = Field(default=None, max_length=5000)
    options: Optional[list[QuestionOptionIn]] = Field(
        default=None, description="单选/多选：2~6 项，至少 1 个正确"
    )
    judgeAnswer: Optional[bool] = Field(default=None, description="判断题正确答案")
    referenceAnswer: Optional[str] = Field(default=None, max_length=5000, description="简答题参考答案（可空）")


class QuestionUpdate(QuestionCreate):
    """编辑题目（同新增全量；status 只读不接收）。"""


class QuestionOptionOut(BaseModel):
    key: str
    content: str
    isCorrect: bool


class QuestionStats(BaseModel):
    answerCount: int
    correctCount: int
    accuracy: float  # 百分比，1 位小数


class QuestionDetail(BaseModel):
    id: int
    stageId: int
    subjectName: str
    stageName: str
    type: str
    difficulty: str
    content: str
    tags: list[str]
    analysis: Optional[str] = None
    options: list[QuestionOptionOut]
    judgeAnswer: Optional[bool] = None
    referenceAnswer: Optional[str] = None
    status: str
    createdAt: str
    createdBy: Optional[str] = None
    stats: QuestionStats


class QuestionReview(BaseModel):
    result: str = Field(pattern="^(pass|reject)$")


class QuestionBatchStatus(BaseModel):
    action: str = Field(pattern="^(submit|unpublish)$")
    ids: list[int] = Field(min_length=1, max_length=500)


class QuestionBatchReview(BaseModel):
    """批量审核（仅待审核可审，不合法条目跳过并回传 skipped）。"""

    result: str = Field(pattern="^(pass|reject)$")
    ids: list[int] = Field(min_length=1, max_length=500)


class QuestionBatchDelete(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


class QuestionImportPreviewRow(BaseModel):
    rowNo: int
    content: str  # 题干截断
    subjectName: str
    stageName: str
    type: str
    difficulty: str
