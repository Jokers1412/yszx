"""学科管理演示数据（开发/演示用，04 §4.3 页面测试数据）。

内容与 prototype/assets/js/data.js 演示口径一致：
  9 个学科（含无阶段的「其他学科」兜底）+ 19 个阶段 + 16 道示例题目（含选项/答案/解析）。
题目 type/difficulty/status 入库为数值枚举（03 §4）；示例题覆盖各阶段，未覆盖阶段显示 0 题为正常现象。

幂等：同名有效学科已存在则整组跳过（不覆盖手改数据）。
运行：cd backend && .venv/Scripts/python.exe scripts/seed_demo_content.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.modules.content.models import Question, QuestionOption, Stage, Subject  # noqa: E402

# 题型/难度数值枚举（03 §4）
TYPE = {"single": 1, "multi": 2, "judge": 3, "short": 4}
DIFF = {"easy": 1, "medium": 2, "hard": 3}

# q = (题型, 难度, 状态, 题干, 解析, 选项[(key, 文本, 是否正确)], 判断答案, 参考答案, 标签)
# 判断题 answer "T"/"F" → judge_answer 1/0；简答 refAnswer → reference_answer
DEMO_SUBJECTS = [
    {
        "name": "AI应用与智能体开发", "icon": "🤖",
        "description": "面向大模型应用与 Agent 全栈开发能力培养",
        "themeColor": "#2a78d6",
        "stages": [
            {"icon": "📖", "name": "大模型基础", "questions": [
                ("single", "easy", 1,
                 "下列关于大语言模型（LLM）的描述，正确的是？",
                 "大语言模型通过在海量文本语料上进行预训练，学习语言的统计规律与知识表示，再通过微调、提示工程适配下游任务。",
                 [("A", "LLM 只能处理英文文本", 0), ("B", "LLM 通过海量文本预训练学习语言规律", 1),
                  ("C", "LLM 的参数量越小效果一定越好", 0), ("D", "LLM 不需要任何微调即可用于所有场景", 0)],
                 None, None, ["大模型", "基础概念"]),
                ("judge", "easy", 1,
                 "Token 是大模型处理文本的最小单位，一个汉字一定只对应一个 Token。",
                 "Token 切分取决于分词器（Tokenizer）与具体语料，一个汉字可能对应一个或多个 Token，也可能多个汉字共用 Token。",
                 [], 0, None, ["Token"]),
            ]},
            {"icon": "✍️", "name": "Prompt 工程", "questions": [
                ("single", "medium", 1,
                 "在 Prompt 工程中，「Few-shot」指的是？",
                 "Few-shot（少样本提示）是在提示词中给出少量示例，引导模型按示例的模式完成任务；零示例称为 Zero-shot。",
                 [("A", "不给模型任何示例", 0), ("B", "在提示词中给出少量输入输出示例", 1),
                  ("C", "对模型进行全参数微调", 0), ("D", "限制模型输出长度", 0)],
                 None, None, ["Prompt", "Few-shot"]),
                ("single", "hard", 3,
                 "为减少大模型幻觉，下列提示词策略中最有效的是？",
                 "在提示词中明确「不确定时承认不知道、给出依据」能显著抑制幻觉；输出更长反而可能增加编造，温度过高会降低稳定性。",
                 [("A", "要求模型「不知道就说不知道」并提供依据来源", 1), ("B", "让模型每次输出越长越好", 0),
                  ("C", "删除所有系统提示", 0), ("D", "随机化温度参数到 2.0", 0)],
                 None, None, ["幻觉", "Prompt"]),
            ]},
            {"icon": "🧠", "name": "Agent 开发", "questions": [
                ("multi", "medium", 1,
                 "以下哪些属于 AI Agent 的核心组成部分？（多选）",
                 "AI Agent 通常由规划、记忆、工具使用与大模型核心四部分组成，硬盘分区属于操作系统概念。",
                 [("A", "规划（Planning）", 1), ("B", "记忆（Memory）", 1),
                  ("C", "工具使用（Tool Use）", 1), ("D", "硬盘分区", 0)],
                 None, None, ["Agent"]),
                ("single", "medium", 1,
                 "ReAct 框架中，Agent 的一次典型循环是？",
                 "ReAct 将推理（Reasoning）与行动（Acting）交替进行：先思考下一步，再调用工具行动，然后观察结果，循环直至完成任务。",
                 [("A", "思考 → 行动 → 观察", 1), ("B", "输入 → 输出", 0),
                  ("C", "训练 → 评估", 0), ("D", "编码 → 部署", 0)],
                 None, None, ["Agent", "ReAct"]),
            ]},
            {"icon": "🚀", "name": "项目实战", "questions": [
                ("short", "hard", 1,
                 "请简述 RAG（检索增强生成）的原理，并说明它解决了大模型的哪些问题。",
                 "RAG 将外部知识库检索与大模型生成结合：先根据用户问题检索相关文档片段，再将片段作为上下文注入提示词由模型生成答案。",
                 [], None,
                 "RAG（检索增强生成）在生成前先从外部知识库中检索与问题相关的文档片段，将其作为上下文注入 Prompt，再由大模型生成答案。它解决了：① 知识截止日期问题（可接入实时更新的资料）；② 幻觉问题（生成有据可依）；③ 领域私有知识缺失（无需重新训练即可使用企业内部资料）。",
                 ["RAG", "项目实战"]),
            ]},
        ],
    },
    {
        "name": "AI大模型开发", "icon": "🧬",
        "description": "深度学习、微调与推理部署全流程",
        "themeColor": "#6250d6",
        "stages": [
            {"icon": "📐", "name": "深度学习基础", "questions": [
                ("single", "easy", 1,
                 "神经网络中，激活函数的主要作用是？",
                 "没有激活函数的多层网络等价于单层线性变换，激活函数引入非线性，使网络可以拟合复杂函数。",
                 [("A", "引入非线性表达能力", 1), ("B", "加快数据读取", 0),
                  ("C", "压缩模型体积", 0), ("D", "初始化权重", 0)],
                 None, None, ["深度学习"]),
            ]},
            {"icon": "🔧", "name": "大模型微调", "questions": [
                ("multi", "hard", 1,
                 "大模型参数高效微调（PEFT）的常见方法有哪些？（多选）",
                 "LoRA、Prompt Tuning、Adapter 都只训练少量新增参数，属于参数高效微调；全参数预训练不属于微调手段且成本极高。",
                 [("A", "LoRA", 1), ("B", "Prompt Tuning", 1),
                  ("C", "全参数预训练", 0), ("D", "Adapter", 1)],
                 None, None, ["微调", "LoRA"]),
            ]},
            {"icon": "📦", "name": "推理与部署", "questions": [
                ("judge", "medium", 1,
                 "模型量化（INT8/INT4）可以在基本保持效果的同时显著降低推理显存占用。",
                 "量化将权重与激活从高精度浮点映射到低比特整数，显著降低显存与算力需求，配合校准通常效果损失很小。",
                 [], 1, None, ["量化", "部署"]),
            ]},
        ],
    },
    {
        "name": "AI具身智能机器人开发", "icon": "🦾",
        "description": "机器人感知、控制与规划一体化训练",
        "themeColor": "#1baf7a",
        "stages": [
            {"icon": "🤖", "name": "机器人学基础", "questions": [
                ("single", "medium", 1,
                 "机器人运动学中，正运动学（Forward Kinematics）解决的问题是？",
                 "正运动学由各关节角度推算末端执行器的位置与姿态；反运动学（IK）则相反，由目标位姿反解关节角度。",
                 [("A", "由关节角度求末端执行器位姿", 1), ("B", "由末端位姿求关节角度", 0),
                  ("C", "求机器人质量", 0), ("D", "规划避障路径", 0)],
                 None, None, ["运动学"]),
            ]},
            {"icon": "🎮", "name": "运动控制", "questions": []},
            {"icon": "👁️", "name": "感知与规划", "questions": []},
        ],
    },
    {
        "name": "AI嵌入式_机器人开发", "icon": "🔌",
        "description": "嵌入式系统与机器人驱动开发",
        "themeColor": "#eb6834",
        "stages": [
            {"icon": "💾", "name": "嵌入式基础", "questions": []},
            {"icon": "⚙️", "name": "驱动开发", "questions": []},
        ],
    },
    {
        "name": "AI测试", "icon": "🧪",
        "description": "功能、自动化与 AI 专项测试能力",
        "themeColor": "#e87ba4",
        "stages": [
            {"icon": "📋", "name": "测试基础", "questions": [
                ("single", "easy", 1,
                 "软件测试中，「黑盒测试」关注的是？",
                 "黑盒测试不关心内部实现，只依据需求验证输入与输出是否符合预期，常见方法有等价类划分、边界值分析等。",
                 [("A", "程序内部逻辑结构", 0), ("B", "输入与输出的对应关系", 1),
                  ("C", "代码行覆盖率", 0), ("D", "变量命名规范", 0)],
                 None, None, ["测试基础"]),
            ]},
            {"icon": "🔁", "name": "自动化测试", "questions": []},
            # 状态 0 禁用：演示禁用态阶段展示（题目计数仍在）
            {"icon": "🤖", "name": "AI 专项测试", "status": 0, "questions": [
                ("multi", "medium", 3,
                 "针对大模型应用的测试重点包括哪些？（多选）",
                 "大模型应用测试重点关注输出质量（幻觉、一致性）、安全（提示注入、越狱）与非功能指标（延迟、稳定性），像素对齐属于 UI 还原范畴。",
                 [("A", "输出事实一致性（幻觉检测）", 1), ("B", "提示词注入等安全风险", 1),
                  ("C", "响应延迟与稳定性", 1), ("D", "界面像素对齐", 0)],
                 None, None, ["AI测试"]),
            ]},
        ],
    },
    {
        "name": "AI运维", "icon": "☁️",
        "description": "Linux、容器云原生与智能运维",
        "themeColor": "#008300",
        "stages": [
            {"icon": "🐧", "name": "Linux 基础", "questions": [
                ("single", "easy", 1,
                 "Linux 中，用于查看当前工作目录的命令是？",
                 "pwd（print working directory）打印当前工作目录；ls 列出目录内容；cd 切换目录；top 查看进程。",
                 [("A", "pwd", 1), ("B", "ls", 0), ("C", "cd", 0), ("D", "top", 0)],
                 None, None, ["Linux"]),
            ]},
            {"icon": "📦", "name": "容器与 K8s", "questions": [
                ("judge", "medium", 1,
                 "Kubernetes 中，Deployment 会自动维持期望的 Pod 副本数。",
                 "Deployment 通过 ReplicaSet 维持期望副本数，Pod 异常退出或节点故障时自动重建。",
                 [], 1, None, ["K8s"]),
            ]},
            {"icon": "📈", "name": "监控与运维", "questions": []},
        ],
    },
    {
        "name": "AI视觉设计", "icon": "🎨",
        "description": "设计基础与 AIGC 绘图创作",
        "themeColor": "#eda100",
        "stages": [
            {"icon": "🖌️", "name": "设计基础", "questions": []},
            {"icon": "🖼️", "name": "AIGC 绘图", "questions": [
                ("short", "medium", 1,
                 "请简述 AIGC 绘图中「提示词（Prompt）」的常用结构，并举例说明。",
                 "常用结构为：主体 + 风格 + 细节修饰 + 负向提示 + 参数（比例、采样器等）。",
                 [], None,
                 "常用 Prompt 结构：① 主体（画面内容，如「一位宇航员」）；② 风格（如「赛博朋克插画风」）；③ 细节修饰（光影、构图、色彩）；④ 负向提示（排除元素，如「模糊、变形」）；⑤ 参数（画幅比例、采样步数）。示例：「一位宇航员站在火星地表，赛博朋克插画风，逆光剪影，8k 细节，--ar 16:9」。",
                 ["AIGC", "绘图"]),
            ]},
        ],
    },
    {
        "name": "AI视频与短剧创作", "icon": "🎬",
        "description": "分镜脚本与 AI 视频工具实战",
        "themeColor": "#e34948",
        "stages": [
            {"icon": "📝", "name": "分镜与脚本", "questions": []},
            {"icon": "🎥", "name": "AI 视频工具", "questions": []},
        ],
    },
    {
        "name": "其他学科", "icon": "📚",
        "description": "兜底分类，暂未规划阶段",
        "themeColor": "#898781",
        "stages": [],
    },
]


async def main() -> None:
    async with SessionLocal() as db:
        created_subjects = 0
        for si, sub in enumerate(DEMO_SUBJECTS, start=1):
            exists = (
                await db.execute(
                    select(Subject.id).where(
                        Subject.name == sub["name"], Subject.deleted_at.is_(None)
                    )
                )
            ).scalar_one_or_none()
            if exists is not None:
                print(f"[跳过] 学科「{sub['name']}」已存在")
                continue

            subject = Subject(
                name=sub["name"],
                icon=sub["icon"],
                description=sub["description"],
                theme_color=sub["themeColor"],
                sort_order=si,
            )
            db.add(subject)
            await db.flush()

            q_total = 0
            for sti, st in enumerate(sub["stages"], start=1):
                stage = Stage(
                    subject_id=subject.id,
                    name=st["name"],
                    icon=st.get("icon"),
                    sort_order=sti,
                    status=st.get("status", 1),
                )
                db.add(stage)
                await db.flush()

                for qi, q in enumerate(st["questions"], start=1):
                    qtype, diff, status, content, analysis, options, judge, ref, tags = q
                    question = Question(
                        stage_id=stage.id,
                        type=TYPE[qtype],
                        difficulty=DIFF[diff],
                        status=status,
                        content=content,
                        judge_answer=judge,
                        reference_answer=ref,
                        analysis=analysis,
                        tags=tags,
                    )
                    db.add(question)
                    await db.flush()
                    q_total += 1

                    for oi, (key, text, correct) in enumerate(options, start=1):
                        db.add(
                            QuestionOption(
                                question_id=question.id,
                                option_key=key,
                                content=text,
                                is_correct=correct,
                                sort_order=oi,
                            )
                        )

            created_subjects += 1
            print(f"[新增] 学科「{sub['name']}」：{len(sub['stages'])} 阶段 / {q_total} 题")

        await db.commit()
        print(f"完成：新增 {created_subjects} 个学科（其余已存在跳过）")


if __name__ == "__main__":
    asyncio.run(main())
