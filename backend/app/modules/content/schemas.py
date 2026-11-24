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
