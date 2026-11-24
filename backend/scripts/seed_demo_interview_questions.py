"""面试题库演示数据（开发/演示用，04 §4.6 页面测试数据）。

内容取自 prototype/admin/interview-questions.html 导入示例（12 道），学科与
seed_demo_content.py 的演示学科对应；混合两种来源（手工录入 / Excel 导入带文件名+行号），
其中 1 道留空主题演示「未分类」状态。

幂等：同题干的有效面试题已存在则跳过。
运行：cd backend && .venv/Scripts/python.exe scripts/seed_demo_interview_questions.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.modules.content.models import Subject  # noqa: E402
from app.modules.interview.models import InterviewQuestion  # noqa: E402

# (学科, 题干, 难度1简单/2中等/3困难, 主题, 标签, 参考答案, 来源 manual|excel, 行号)
IMPORT_FILE = "面试题批量导入-202611.xlsx"
DEMO_QUESTIONS = [
    ("AI应用与智能体开发", "请说明 Agent 记忆的短期与长期记忆如何设计？", 2, "Agent", ["记忆", "Agent"],
     "短期记忆用会话上下文，长期记忆用向量库沉淀并检索。", "excel", 1),
    ("AI应用与智能体开发", "提示词模板在工程上如何管理与版本化？", 1, "Prompt", ["提示词", "工程化"],
     "模板纳入配置中心与版本控制，配套回归评测。", "excel", 2),
    ("AI大模型开发", "什么是 MoE（专家混合）结构？它带来什么收益？", 3, "深度学习", ["MoE"],
     "将 FFN 拆成多个专家按路由激活，参数量大而计算量可控。", "excel", 3),
    ("AI大模型开发", "vLLM 的 PagedAttention 解决了什么问题？", 2, "部署", ["vLLM", "推理"],
     "解决 KV Cache 显存碎片与浪费，提升并发吞吐。", "excel", 4),
    ("AI运维", "如何为 Kubernetes 工作负载配置 HPA？", 2, "K8s", ["HPA", "K8s"],
     "按 CPU / 自定义指标设定目标值与副本范围。", "excel", 5),
    ("AI测试", "大模型输出的回归测试如何做？", 2, "AI测试", ["回归测试"],
     "固定提示集 + 自动评分器 + 阈值告警。", "excel", 6),
    ("AI应用与智能体开发", "多轮对话中如何维护会话状态？", 2, "提示工程", ["对话状态"],
     "用会话窗口 + 状态摘要，必要时落库。", "excel", 7),
    ("AI视觉设计", "如何评估 AIGC 出图与提示词的一致性？", 1, "AIGC绘图", ["评估"],
     "人工评分结合 VQA 自动评分。", "excel", 8),
    ("AI具身智能机器人开发", "手眼标定的目的是什么？", 3, "感知与规划", ["标定"],
     "求取相机坐标系与末端坐标系的变换关系。", "excel", 10),
    # 手工录入 3 道（演示来源标识与「删除不可恢复」提示）
    ("AI嵌入式_机器人开发", "实时操作系统与 Linux 的关键差异？", 2, "嵌入式", ["RTOS"],
     "确定性调度、低中断延迟、可预测响应时间。", "manual", None),
    ("AI大模型开发", "模型服务的灰度发布有哪些策略？", 1, "部署", ["灰度"],
     "按流量比例、按租户、金丝雀发布逐步放量。", "manual", None),
    # 主题留空 = 未分类（演示筛选与展示）
    ("AI视频与短剧创作", "分镜脚本包含哪些必备要素？", 1, None, ["分镜"],
     "镜号、景别、时长、台词、画面描述、音效。", "manual", None),
]


async def main() -> None:
    async with SessionLocal() as db:
        subject_ids: dict[str, int] = dict(
            (await db.execute(select(Subject.name, Subject.id).where(Subject.deleted_at.is_(None)))).all()
        )
        created = 0
        for subject_name, content, difficulty, topic, tags, ref, source, row_no in DEMO_QUESTIONS:
            if subject_name not in subject_ids:
                print(f"[跳过] 「{subject_name}」不存在（先运行 seed_demo_content.py）")
                continue
            exists = (
                await db.execute(
                    select(InterviewQuestion.id)
                    .where(InterviewQuestion.content == content, InterviewQuestion.deleted_at.is_(None))
                    .limit(1)
                )
            ).scalar_one_or_none()
            if exists is not None:
                print(f"[跳过] 已存在：{content[:20]}…")
                continue

            is_manual = source == "manual"
            db.add(
                InterviewQuestion(
                    subject_id=subject_ids[subject_name],
                    content=content,
                    difficulty=difficulty,
                    topic=topic,
                    tags=tags,
                    reference_answer=ref,
                    source_type=1 if is_manual else 2,
                    source_file=None if is_manual else IMPORT_FILE,
                    source_row=row_no,
                )
            )
            created += 1
            print(f"[新增] ({source}) {content[:24]}…")

        await db.commit()
        print(f"完成：新增 {created} 道面试题（其余已存在跳过）")


if __name__ == "__main__":
    asyncio.run(main())
