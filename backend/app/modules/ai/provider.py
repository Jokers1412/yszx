"""AI 网关：Provider 抽象与工厂（02 D5）。

- 统一封装全部 LLM 能力，屏蔽供应商差异（OpenAI 兼容 / 国产大模型 API）；
- 所有输出做结构化 JSON 校验 + 失败重试，评分等关键字段限幅（0-10）；
- 联调期用 MockProvider；真实供应商后补（仅新增实现与配置，不动业务模块）。
"""
from typing import Any, Optional, Protocol

from app.core.config import get_settings


class AiProvider(Protocol):
    """LLM 能力契约（返回结构化 dict，schema 校验在 service 层补充）。"""

    async def grade_short_answer(
        self, question: str, answer: str, reference: Optional[str] = None
    ) -> dict[str, Any]:
        """简答批改：{score: 0-10, comment, key_points: []}。"""
        ...

    async def generate_interview_questions(
        self, subject: str, difficulty: str, count: int
    ) -> list[dict[str, Any]]:
        """面试出题（AI 补充）：[{content, reference_answer}]。"""
        ...

    async def score_interview_answer(
        self, question: str, answer: str
    ) -> dict[str, Any]:
        """逐题评分：{score: 0-10, comment}。"""
        ...

    async def generate_interview_report(self, session_data: dict[str, Any]) -> dict[str, Any]:
        """整体评价 + 六维能力 + 优缺点 + 建议 + 补强三卡（03 附录 A 结构）。"""
        ...


class MockProvider:
    """联调期 Mock（脚本化输出，对齐原型演示行为）。

    ⚠️ 具体文案/评分策略待功能开发阶段按原型演示行为对齐（02 §7 风险表）。
    """

    async def grade_short_answer(
        self, question: str, answer: str, reference: Optional[str] = None
    ) -> dict[str, Any]:
        raise NotImplementedError("Mock 批改待功能开发阶段实现（对齐原型演示行为）")

    async def generate_interview_questions(
        self, subject: str, difficulty: str, count: int
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Mock 出题待功能开发阶段实现")

    async def score_interview_answer(
        self, question: str, answer: str
    ) -> dict[str, Any]:
        raise NotImplementedError("Mock 评分待功能开发阶段实现")

    async def generate_interview_report(self, session_data: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Mock 报告待功能开发阶段实现")


def get_ai_provider() -> AiProvider:
    provider = get_settings().ai_provider
    if provider == "mock":
        return MockProvider()
    raise ValueError(f"未知 AI 供应商: {provider}（02 D5：供应商确定后在此注册）")
