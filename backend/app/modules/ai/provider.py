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


# AI 补充出题模板（联调期 Mock；{subject} 为面试方向）
_QUESTION_TEMPLATES: list[dict[str, str]] = [
    {
        "q": "请介绍一下你在{subject}方向做过的最有挑战的项目，并说明你承担的角色与最终成果。",
        "a": "建议按 STAR 结构作答：项目背景与目标、你负责的模块、遇到的关键难点与解决方案、可量化的最终成果。",
    },
    {
        "q": "请解释一个{subject}方向的核心概念，并说明它在实际项目中的应用场景。",
        "a": "先给出概念的准确定义与关键组成，再结合一个具体场景说明其作用、边界与常见误区。",
    },
    {
        "q": "在{subject}的项目中，你是如何定位并解决一个线上问题的？",
        "a": "描述问题现象、排查思路与工具、根因分析、修复与验证过程，并总结预防措施。",
    },
    {
        "q": "如果让你从零设计一个{subject}相关的系统，你会如何做技术选型与架构设计？",
        "a": "从需求与约束出发，说明关键技术的选型理由、架构分层、数据流与扩展性、可靠性权衡。",
    },
    {
        "q": "{subject}方向的技术更新很快，你是如何保持学习并落地到项目中的？",
        "a": "说明信息来源、学习方法、验证与取舍过程，并举一个把新技术落地产生价值的例子。",
    },
    {
        "q": "请分享一次你在{subject}项目中与他人产生技术分歧的经历，以及你的处理方式。",
        "a": "描述分歧背景、双方观点、你用数据/实验推动决策的方式、最终结果与反思。",
    },
    {
        "q": "在{subject}方向，你认为自己最需要补齐的能力是什么？准备如何提升？",
        "a": "诚实评估短板，给出具体的学习计划、实践路径与检验标准。",
    },
    {
        "q": "请描述一次你在{subject}项目中面对紧急交付压力的经历，如何保证质量？",
        "a": "说明优先级取舍、并行协作、质量保障手段与最终交付结果。",
    },
]


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
        """按模板生成面试题（题库不足时的补充题，Q4）。"""
        await asyncio.sleep(0.3)
        level = {"easy": "基础", "medium": "进阶", "hard": "高阶"}.get(difficulty, "进阶")
        out = []
        for i in range(count):
            tpl = _QUESTION_TEMPLATES[i % len(_QUESTION_TEMPLATES)]
            out.append(
                {
                    "content": f"【{level}】" + tpl["q"].format(subject=subject),
                    "reference_answer": tpl["a"].format(subject=subject),
                }
            )
        return out

    async def score_interview_answer(
        self, question: str, answer: str
    ) -> dict[str, Any]:
        """面试作答启发式评分（联调期 Mock）。"""
        await asyncio.sleep(0.8)  # 模拟评分延迟，供前端展示「分析中 → 评分中 → 思考中」
        text = (answer or "").strip()
        score = 5
        if len(text) >= 50:
            score += 1
        if len(text) >= 150:
            score += 1
        if len(text) >= 300:
            score += 1
        if re.search(r"(首先|其次|然后|最后|因为|比如|例如|总结)", text):
            score += 1
        if re.search(r"[。！？；;]", text):
            score += 1
        score = max(0, min(10, score))
        if score >= 8:
            comment = "回答结构完整、要点清晰，能结合实际展开，体现出较好的专业表达；如能补充量化结果会更有说服力。"
        elif score >= 6:
            comment = "回答覆盖了主要要点，思路基本清晰；建议补充具体示例与细节，让表达更具说服力。"
        else:
            comment = "回答较为简略，关键要点未能充分展开；建议围绕问题分层作答，并结合项目经验举例说明。"
        return {"score": score, "comment": comment}

    async def generate_interview_report(self, session_data: dict[str, Any]) -> dict[str, Any]:
        """面试报告生成（整体评价/六维/优缺点/建议/补强 + 结束语）。"""
        await asyncio.sleep(0.5)
        avg = float(session_data.get("avg") or 0)
        subject = str(session_data.get("subject") or "")
        offsets = {"专业基础": 0.4, "表达沟通": -0.2, "逻辑思维": 0.2, "项目经验": -0.3, "应变能力": 0.1, "岗位匹配": 0.3}
        ability = {k: round(max(0.0, min(10.0, avg + off)), 1) for k, off in offsets.items()}
        if avg >= 8:
            overall = f"本场{subject}方向面试整体表现优秀，回答专业扎实、表达流畅，展现出较强的岗位竞争力。"
            strengths = ["专业概念掌握扎实，回答问题时术语使用准确", "表达流畅有条理，能抓住重点展开"]
            improvements = [
                {"issue": "个别回答可进一步量化呈现结果", "advice": "建议用数据与效果描述项目成果，增强说服力"},
                {"issue": "开放性问题的收尾可以更干脆", "advice": "建议先给结论再展开论证，控制在 2 分钟内讲清一件事"},
            ]
        elif avg >= 6:
            overall = f"本场{subject}方向面试表现良好，基础较为扎实，部分回答的深度与细节还有提升空间。"
            strengths = ["表达流畅有条理，能抓住重点展开", "分析问题逻辑清晰，能分层递进"]
            improvements = [
                {"issue": "部分基础概念表述还不够严谨", "advice": "建议系统复习核心概念，并用自己的话复述形成闭环"},
                {"issue": "项目中的个人贡献与难点剖析不够深入", "advice": "建议按 STAR 结构复盘项目，突出你解决的关键问题"},
            ]
        else:
            overall = f"本场{subject}方向面试暴露了一些知识短板，建议针对性补强后再战。"
            strengths = ["面对追问反应较快，能灵活调整思路"]
            improvements = [
                {"issue": "核心要点覆盖不完整", "advice": "建议系统复习核心概念，并用自己的话复述形成闭环"},
                {"issue": "回答展开不足、缺少示例", "advice": "建议先给结论再展开论证，结合项目经验举例说明"},
            ]
        return {
            "overall_comment": overall,
            "ability_scores": ability,
            "strengths": strengths,
            "improvements": improvements,
            "suggestions": [
                "围绕薄弱维度做专项补强，把每次错题沉淀进错题本，连续答对 3 次即可标记已掌握。",
                "复盘本次全部作答，把表述不完整的要点写成 3 句话版本，反复练习到脱口而出。",
                "结合错题本与专项题库巩固薄弱知识点，再预约一场同方向模拟面试检验效果。",
            ],
            "coaching": {
                "questions": "针对薄弱知识点刷专项题，把每次错题沉淀进错题本，连续答对 3 次即可标记已掌握。",
                "courses": "沿学习路线补齐大模型基础与项目实战课程，带着面试中暴露的短板去看，吸收效率更高。",
                "reinterview": "复盘完本次报告后，再来一场同方向面试，检验改进效果。",
            },
            "end_remark": "以上就是本次面试的全部问题，感谢你的作答！完整评分与改进建议已生成，你可以前往面试报告查看。",
        }


def get_ai_provider() -> AiProvider:
    provider = get_settings().ai_provider
    if provider == "mock":
        return MockProvider()
    raise ValueError(f"未知 AI 供应商: {provider}（02 D5：供应商确定后在此注册）")
