"""ai 输出结构化校验模型（Pydantic：ScoreResult / GradeResult / ReportResult 等）。

本文件随功能开发逐步补充；校验失败按 S2 降级为 SYS_AI_UNAVAILABLE。
字段命名与 03 附录 A 的 DB JSON 结构一致（snake_case，如 key_points）。
"""
from typing import Optional

from pydantic import BaseModel, Field


class GradeResult(BaseModel):
    """简答批改结果（03 附录 A：{score, comment, key_points}）。"""

    score: int = Field(ge=0, le=10)
    comment: str
    key_points: list[str]


class ScoreResult(BaseModel):
    """面试逐题评分（0-10，03 §2.4.3）。"""

    score: int = Field(ge=0, le=10)
    comment: str = Field(max_length=1000)


class GeneratedQuestion(BaseModel):
    """AI 补充生成的面试题（Q4：题库不足时补充）。"""

    content: str
    reference_answer: Optional[str] = None


ABILITY_KEYS = ["专业基础", "表达沟通", "逻辑思维", "项目经验", "应变能力", "岗位匹配"]


class InterviewReportResult(BaseModel):
    """面试报告生成结果（03 §2.4.4 / 附录 A；end_remark 不落库 S21）。"""

    overall_comment: str
    ability_scores: dict[str, float]  # 六固定键 → 0-10
    strengths: list[str]
    improvements: list[dict[str, str]]  # [{issue, advice}]
    suggestions: list[str]
    coaching: dict[str, str]  # {questions, courses, reinterview}
    end_remark: str
