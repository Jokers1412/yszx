"""interview 请求/响应模型（04 §4.6 面试题库管理；§4.13 AI 面试后续补充）。

主题为自由文本（01 阶段 11 确认 D4-20：无词表下拉/词表外标注，筛选模糊匹配）；
来源记 Excel 文件名 + 数据行序号（A2），手工录入 sourceType=manual。
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

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
