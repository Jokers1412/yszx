"""content 请求/响应模型（04 §4.3 学科管理；§4.4-4.7 课程/题目/路线后续补充）。

命名约定（04 §1.1）：JSON lowerCamelCase；不返回 deletedAt 等内部字段；
status 采用字符串枚举 enabled|disabled（04 附录 C），入库转 1|0。
"""
from typing import Optional

from pydantic import BaseModel, Field


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
