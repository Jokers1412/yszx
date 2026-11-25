"""ai 业务服务：编排 Provider 调用 + 结构化校验 + 失败重试 + 评分限幅（0-10）。

对外暴露简答批改与面试三能力（出题/逐题评分/报告）。
失败口径 S2：AI 不可用/输出不合规 → 抛 BizError(SYS_AI_UNAVAILABLE, 503)，
不落业务记录、前端可重试；内部细节不外泄（仅记内部异常）。
"""
import logging
from typing import Any, Optional

from app.common.error_codes import ErrorCode
from app.core.exceptions import BizError
from app.modules.ai.provider import get_ai_provider
from app.modules.ai.schemas import (
    ABILITY_KEYS,
    GeneratedQuestion,
    GradeResult,
    InterviewReportResult,
    ScoreResult,
)

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 2  # 首次 + 重试 1 次（02 D5：输出不合规视同失败重试）


async def _call_with_retry(label: str, fn, message: str = "AI 服务暂不可用，请稍后重试") -> Any:
    """Provider 调用 + 重试；失败统一降级 503（S2）。"""
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return await fn()
        except Exception as exc:  # Provider 异常/输出不合规 → 重试后统一降级
            logger.warning("%s失败（第 %s 次）: %s", label, attempt + 1, exc)
    raise BizError(ErrorCode.SYS_AI_UNAVAILABLE, message, http_status=503)


def _validated_grade(raw: Any) -> dict:
    """校验/规整批改输出（限幅 score 0-10），不合规抛 ValueError 交由重试。"""
    if not isinstance(raw, dict):
        raise ValueError("批改输出不是对象")
    score = int(round(float(raw["score"])))
    grade = GradeResult(
        score=max(0, min(10, score)),
        comment=str(raw.get("comment") or "").strip()[:500],
        key_points=[str(k).strip()[:50] for k in (raw.get("key_points") or []) if str(k).strip()][:5],
    )
    return grade.model_dump()


async def grade_short_answer(
    question: str, answer: str, reference: Optional[str] = None
) -> dict:
    """简答批改：{score: 0-10, comment, key_points}；失败 → 503 SYS_AI_UNAVAILABLE（S2）。"""
    provider = get_ai_provider()

    async def _call():
        return _validated_grade(await provider.grade_short_answer(question, answer, reference))

    return await _call_with_retry("简答批改", _call, message="AI 批改暂不可用，请稍后重试")


async def score_interview_answer(question: str, answer: str) -> dict:
    """面试逐题评分：{score: 0-10, comment}（S2 失败 503 可重试）。"""
    provider = get_ai_provider()

    async def _call():
        raw = await provider.score_interview_answer(question, answer)
        if not isinstance(raw, dict):
            raise ValueError("评分输出不是对象")
        score = int(round(float(raw["score"])))
        result = ScoreResult(
            score=max(0, min(10, score)),
            comment=str(raw.get("comment") or "").strip()[:1000],
        )
        return result.model_dump()

    return await _call_with_retry("面试评分", _call)


async def generate_interview_questions(subject: str, difficulty: str, count: int) -> list[dict]:
    """AI 补充出题（Q4）：[{content, reference_answer}]。"""
    provider = get_ai_provider()

    async def _call():
        raw = await provider.generate_interview_questions(subject, difficulty, count)
        if not isinstance(raw, list):
            raise ValueError("出题输出不是列表")
        items = [GeneratedQuestion.model_validate(x).model_dump() for x in raw[:count]]
        if len(items) != count:
            raise ValueError("出题数量不足")
        return items

    return await _call_with_retry("面试出题", _call)


async def generate_interview_report(session_data: dict) -> dict:
    """面试报告生成（整体评价/六维/优缺点/建议/补强 + end_remark）。"""
    provider = get_ai_provider()

    async def _call():
        raw = await provider.generate_interview_report(session_data)
        result = InterviewReportResult.model_validate(raw)
        if set(result.ability_scores) != set(ABILITY_KEYS):
            raise ValueError("六维能力键不完整")
        data = result.model_dump()
        data["ability_scores"] = {
            k: round(max(0.0, min(10.0, float(v))), 1) for k, v in data["ability_scores"].items()
        }
        return data

    return await _call_with_retry("面试报告生成", _call)
