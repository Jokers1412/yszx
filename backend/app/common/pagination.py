"""分页模型（04 §1.3 定稿）。

入参：pageNum（从 1 起，默认 1）、pageSize（默认 10，上限 100）；
出参 data 内：{ list, total, pageNum, pageSize }。
"""
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.common.constants import PAGE_NUM_MIN, PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX

T = TypeVar("T")


class PageQuery(BaseModel):
    """列表接口统一查询参数。"""

    pageNum: int = Field(default=PAGE_NUM_MIN, ge=PAGE_NUM_MIN)
    pageSize: int = Field(default=PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX)

    @property
    def offset(self) -> int:
        return (self.pageNum - 1) * self.pageSize

    @property
    def limit(self) -> int:
        return self.pageSize


class PageResult(BaseModel, Generic[T]):
    list: list[T]
    total: int
    pageNum: int
    pageSize: int
