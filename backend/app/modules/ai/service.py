"""ai 业务服务：编排 Provider 调用 + 结构化校验 + 失败重试 + 评分限幅（0-10）。

对外暴露简答批改接口（本期待用）；出题/逐题评分/报告随面试功能补充。
失败口径 S2：AI 不可用/输出不合规 → 抛 BizError(SYS_AI_UNAVAILABLE, 503)，
不落业务记录、前端可重试；内部细节不外泄（仅记内部异常）。
"""
import logging
from typing import Any, Optional

from app.common.error_codes import ErrorCode
from app.core.exceptions import BizError
from app.modules.ai.provider import get_ai_provider
from app.modules.ai.schemas import GradeResult

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 2  # 首次 + 重试 1 次（02 D5：输出不合规视同失败重试）


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
    for attempt in range(_MAX_ATTEMPTS):
        try:
            raw = await provider.grade_short_answer(question, answer, reference)
            return _validated_grade(raw)
        except Exception as exc:  # Provider 异常/输出不合规 → 重试后统一降级
            logger.warning("简答批改失败（第 %s 次）: %s", attempt + 1, exc)
    raise BizError(ErrorCode.SYS_AI_UNAVAILABLE, "AI 批改暂不可用，请稍后重试", http_status=503)
