"""B站课程库演示数据（开发/演示用，04 §4.4 页面测试数据）。

内容与 prototype/assets/js/data.js 演示口径一致：14 门课程，关联学科与
scripts/seed_demo_content.py 的 9 个演示学科一一对应（含「其他学科」1 门）。
sort_seq 按 03 §5.2 S5 非导入段位赋值：列表展示顺序 = data.js 顺序，后续手动新增自动排在最前。

幂等：同名+同来源（或同 BV号）的有效课程已存在则跳过。
运行：cd backend && .venv/Scripts/python.exe scripts/seed_demo_courses.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import or_, select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.modules.content.models import Course, CourseSubject, Subject  # noqa: E402
from app.modules.content.service import _MANUAL_SORT_BASE  # noqa: E402  # 与服务层同源口径

# (名称, BV号, 时长分钟, [学科名], 来源 1B站/2其他)
DEMO_COURSES = [
    ("大模型应用开发实战：从 Prompt 到 Agent", "BV1xK4y1E7qA", 390, ["AI应用与智能体开发"], 1),
    ("LangChain 与 RAG 项目实战教程", "BV1dS4y1m7cR", 255, ["AI应用与智能体开发", "AI大模型开发"], 1),
    ("深度学习入门：神经网络基础", "BV1aT411N7mV", 480, ["AI大模型开发"], 1),
    ("大模型微调实战（LoRA / QLoRA）", "BV1hJ411x7pQ", 225, ["AI大模型开发"], 1),
    ("ROS2 机器人开发从入门到实践", "BV1mC4y1P7kL", 320, ["AI具身智能机器人开发"], 1),
    ("嵌入式 Linux 驱动开发精讲", "BV1rN4y1T7bW", 430, ["AI嵌入式_机器人开发"], 1),
    ("软件测试全流程：从用例设计到自动化", "BV1sY4y1k7dM", 350, ["AI测试"], 1),
    ("Docker 与 Kubernetes 实战", "BV1pQ4y1v7cX", 365, ["AI运维"], 1),
    ("Prometheus 智能监控体系搭建", "BV1wE4y1r7tY", 160, ["AI运维"], 1),
    ("AIGC 绘图：Midjourney 与 Stable Diffusion", "BV1uI4y1o7uZ", 240, ["AI视觉设计"], 1),
    ("AI 短剧创作：分镜脚本与成片实战", "BV1yH4y1i7oP", 200, ["AI视频与短剧创作"], 1),
    ("Agent 开发进阶：多智能体协作", "BV1zM4y1a7sD", 175, ["AI应用与智能体开发"], 1),
    ("面试高频算法题精讲（内部资料）", None, 90, ["其他学科"], 2),
    ("大模型推理加速：vLLM 部署实践", "BV1gF4y1e7qS", 135, ["AI大模型开发", "AI应用与智能体开发"], 1),
]


async def main() -> None:
    async with SessionLocal() as db:
        subject_ids: dict[str, int] = dict(
            (await db.execute(select(Subject.name, Subject.id).where(Subject.deleted_at.is_(None)))).all()
        )
        n = len(DEMO_COURSES)
        created = 0
        for pos, (name, bvid, minutes, subject_names, source) in enumerate(DEMO_COURSES, start=1):
            missing = [s for s in subject_names if s not in subject_ids]
            if missing:
                print(f"[跳过] 「{name}」：学科不存在 {missing}（先运行 seed_demo_content.py）")
                continue

            dup = await db.execute(
                select(Course.id)
                .where(
                    Course.deleted_at.is_(None),
                    or_(Course.bvid == bvid, (Course.name == name) & (Course.source == source))
                    if bvid
                    else (Course.name == name) & (Course.source == source),
                )
                .limit(1)
            )
            if dup.scalar_one_or_none() is not None:
                print(f"[跳过] 课程「{name}」已存在")
                continue

            course = Course(
                name=name,
                bvid=bvid,
                cover_url=None,  # 演示走 16:10 图标兜底；可自行填 B站封面 URL
                duration_minutes=minutes,
                source=source,
                play_url=f"https://www.bilibili.com/video/{bvid}" if bvid else "",
                # 非导入段位（S5）：按展示序 c1..cn 赋值，ASC 即 data.js 顺序
                sort_seq=_MANUAL_SORT_BASE - n + pos,
            )
            db.add(course)
            await db.flush()
            for i, sname in enumerate(subject_names):
                db.add(
                    CourseSubject(
                        course_id=course.id,
                        subject_id=subject_ids[sname],
                        is_primary=1 if i == 0 else 0,
                    )
                )
            created += 1
            print(f"[新增] {name}（{'、'.join(subject_names)}，{minutes} 分钟）")

        await db.commit()
        print(f"完成：新增 {created} 门课程（其余已存在跳过）")


if __name__ == "__main__":
    asyncio.run(main())
