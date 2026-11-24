"""按 seed_demo_content 的预期状态回填演示题 status（冒烟测试漂移修复，幂等）。

匹配口径：题干文本一致的演示题按种子意图重置 status（其余数据不动）。
运行：cd backend && .venv/Scripts/python.exe scripts/restore_demo_question_status.py
"""
import asyncio
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.modules.content.models import Question  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "seed_demo_content", Path(__file__).resolve().parent / "seed_demo_content.py"
)
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)

# 题干 -> 预期状态
EXPECTED = {}
for sub in seed.DEMO_SUBJECTS:
    for st in sub["stages"]:
        for q in st["questions"]:
            EXPECTED[q[3]] = q[2]  # (题干, status)


async def main() -> None:
    async with SessionLocal() as db:
        rows = (
            (await db.execute(select(Question).where(Question.deleted_at.is_(None)))).scalars().all()
        )
        changed = 0
        for row in rows:
            want = EXPECTED.get(row.content)
            if want is not None and row.status != want:
                print(f"[重置] #{row.id} status {row.status} -> {want}｜{row.content[:24]}")
                row.status = want
                changed += 1
        await db.commit()
        print(f"完成：重置 {changed} 道题状态")


if __name__ == "__main__":
    asyncio.run(main())
