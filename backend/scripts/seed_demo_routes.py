"""学习路线演示数据（开发/演示用，04 §4.7 页面测试数据）。

内容与 prototype/assets/js/data.js 演示口径一致：5 条路线，学科/课程与
seed_demo_content.py、seed_demo_courses.py 的演示数据一一对应（含 1 条禁用路线）。

幂等：同名有效路线已存在则跳过。
运行：cd backend && .venv/Scripts/python.exe scripts/seed_demo_routes.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.modules.content.models import Course, Route, RouteItem, Subject  # noqa: E402

# (名称, 学科名, 图标, 状态, 适合学历, 描述, [课程名...按学习顺序])
DEMO_ROUTES = [
    (
        "AI 应用开发入门路线", "AI应用与智能体开发", "🚀", 1,
        "零基础转行 AI 应用开发的学员",
        "从大模型基础概念到 Agent 项目实战，循序渐进建立 AI 应用开发完整知识体系。",
        [
            "大模型应用开发实战：从 Prompt 到 Agent",
            "LangChain 与 RAG 项目实战教程",
            "Agent 开发进阶：多智能体协作",
            "大模型推理加速：vLLM 部署实践",
        ],
    ),
    (
        "大模型开发进阶路线", "AI大模型开发", "🧬", 1,
        "有深度学习基础、想做大模型研发的学员",
        "覆盖深度学习基础、参数高效微调与推理部署三大能力模块。",
        ["深度学习入门：神经网络基础", "大模型微调实战（LoRA / QLoRA）", "大模型推理加速：vLLM 部署实践"],
    ),
    (
        "AI 运维云原生路线", "AI运维", "☁️", 1,
        "运维工程师转型智能运维",
        "容器化、Kubernetes 与监控体系一条龙。",
        ["Docker 与 Kubernetes 实战", "Prometheus 智能监控体系搭建"],
    ),
    (
        "AI 视觉设计创作路线", "AI视觉设计", "🎨", 1,
        "设计爱好者与转行人群",
        "设计基础 + AIGC 绘图工具双引擎。",
        ["AIGC 绘图：Midjourney 与 Stable Diffusion"],
    ),
    (
        "测试开发进阶路线", "AI测试", "🧪", 0,
        "初中级测试工程师",
        "从测试基础到自动化与 AI 专项测试（路线筹备中）。",
        ["软件测试全流程：从用例设计到自动化"],
    ),
]


async def main() -> None:
    async with SessionLocal() as db:
        subject_ids: dict[str, int] = dict(
            (await db.execute(select(Subject.name, Subject.id).where(Subject.deleted_at.is_(None)))).all()
        )
        course_ids: dict[str, int] = dict(
            (await db.execute(select(Course.name, Course.id).where(Course.deleted_at.is_(None)))).all()
        )
        created = 0
        for name, subject_name, icon, status, audience, desc, course_names in DEMO_ROUTES:
            exists = (
                await db.execute(
                    select(Route.id).where(Route.name == name, Route.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            if exists is not None:
                print(f"[跳过] 路线「{name}」已存在")
                continue
            if subject_name not in subject_ids:
                print(f"[跳过] 「{name}」：学科「{subject_name}」不存在（先运行 seed_demo_content.py）")
                continue
            missing = [c for c in course_names if c not in course_ids]
            if missing:
                print(f"[跳过] 「{name}」：课程不存在 {missing}（先运行 seed_demo_courses.py）")
                continue

            route = Route(
                name=name,
                subject_id=subject_ids[subject_name],
                icon=icon,
                target_education=audience,
                description=desc,
                status=status,
            )
            db.add(route)
            await db.flush()
            for i, cname in enumerate(course_names, start=1):
                db.add(RouteItem(route_id=route.id, course_id=course_ids[cname], sort_order=i))
            created += 1
            print(f"[新增] {name}（{subject_name}，{len(course_names)} 门课程）")

        await db.commit()
        print(f"完成：新增 {created} 条路线（其余已存在跳过）")


if __name__ == "__main__":
    asyncio.run(main())
