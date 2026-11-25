"""AI 网关：Provider 抽象与工厂（02 D5）。

- 统一封装全部 LLM 能力，屏蔽供应商差异（OpenAI 兼容 / 国产大模型 API）；
- 所有输出做结构化 JSON 校验 + 失败重试，评分等关键字段限幅（0-10）；
- 联调期用 MockProvider；真实供应商后补（仅新增实现与配置，不动业务模块）。
"""
import asyncio
import re
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

    简答批改为确定性启发式评分（长度/要点覆盖），文案风格对齐原型演示的 AI 评分卡；
    真实供应商接入后仅替换本类，不动业务模块（02 D5）。
    """

    async def grade_short_answer(
        self, question: str, answer: str, reference: Optional[str] = None
    ) -> dict[str, Any]:
        """启发式评分：{score: 0-10, comment, key_points}（联调期 Mock）。"""
        await asyncio.sleep(0.3)  # 模拟批改延迟，供前端展示「AI 评分中」态
        text = (answer or "").strip()
        ref = (reference or "").strip()

        # 参考答案要点抽取（按常见分隔符切分，取 2~12 字片段）
        points = [
            p.strip()
            for p in re.split(r"[，,；;。.\n、/｜|]", ref)
            if 2 <= len(p.strip()) <= 12
        ][:3]
        if not points:
            points = ["覆盖核心概念", "表述清晰", "可补充实例"]

        # 启发式给分：基础分 + 长度 + 要点覆盖
        score = 5
        if len(text) >= 30:
            score += 1
        if len(text) >= 80:
            score += 1
        covered = sum(1 for p in points if p in text)
        score += min(covered, 2)
        if re.search(r"[。！？；;]", text):
            score += 1
        score = max(0, min(10, score))

        if score >= 8:
            comment = "回答结构清晰，核心要点覆盖到位，表达完整；如能补充具体场景或示例会更有说服力。"
        elif score >= 6:
            comment = "回答基本涵盖了核心要点，思路清晰；建议结合具体场景补充细节，使答案更加完整。"
        else:
            comment = "回答涉及部分要点，但覆盖不够完整；建议围绕参考要点逐项展开，并补充关键细节。"
        return {"score": score, "comment": comment, "key_points": points}

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
