"""ai 输出结构化校验模型（Pydantic：ScoreResult / GradeResult / ReportResult 等）。

本文件随功能开发逐步补充；校验失败按 S2 降级为 SYS_AI_UNAVAILABLE。
字段命名与 03 附录 A 的 DB JSON 结构一致（snake_case，如 key_points）。
"""
from pydantic import BaseModel, Field


class GradeResult(BaseModel):
    """简答批改结果（03 附录 A：{score, comment, key_points}）。"""

    score: int = Field(ge=0, le=10)
    comment: str
    key_points: list[str]
