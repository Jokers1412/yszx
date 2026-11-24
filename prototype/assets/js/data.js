/* ============================================================
   云枢智学 原型 · Mock 数据（无服务端，数据全部走这里）
   全局 window.DB
   ============================================================ */
window.DB = (function () {
  "use strict";

  /* ---------- 枚举 ---------- */
  var typeLabel = { single: "单选", multi: "多选", judge: "判断", short: "简答" };
  var diffLabel = { easy: "简单", medium: "中等", hard: "困难" };
  var qStatus = { online: "已上架", offline: "已下架", pending: "待审核", draft: "草稿", rejected: "已驳回" };

  /* ---------- 学员账号（原型默认登录态，可退出） ---------- */
  var user = { name: "林小雨", phone: "13805716721", email: "linxy@example.com", gender: "保密", role: "学员" };

  /* ---------- 管理员账号 ---------- */
  var admin = { username: "admin", role: "超级管理员", name: "系统管理员" };

  /* ---------- 学科 / 阶段 ---------- */
  var subjects = [
    { id: "sub-1", icon: "🤖", name: "AI应用与智能体开发", desc: "面向大模型应用与 Agent 全栈开发能力培养", color: "#2a78d6", stages: [
      { id: "st-101", icon: "📖", name: "大模型基础", count: 24 },
      { id: "st-102", icon: "✍️", name: "Prompt 工程", count: 31 },
      { id: "st-103", icon: "🧠", name: "Agent 开发", count: 28 },
      { id: "st-104", icon: "🚀", name: "项目实战", count: 18 }
    ]},
    { id: "sub-2", icon: "🧬", name: "AI大模型开发", desc: "深度学习、微调与推理部署全流程", color: "#6250d6", stages: [
      { id: "st-201", icon: "📐", name: "深度学习基础", count: 26 },
      { id: "st-202", icon: "🔧", name: "大模型微调", count: 22 },
      { id: "st-203", icon: "📦", name: "推理与部署", count: 15 }
    ]},
    { id: "sub-3", icon: "🦾", name: "AI具身智能机器人开发", desc: "机器人感知、控制与规划一体化训练", color: "#1baf7a", stages: [
      { id: "st-301", icon: "🤖", name: "机器人学基础", count: 12 },
      { id: "st-302", icon: "🎮", name: "运动控制", count: 14 },
      { id: "st-303", icon: "👁️", name: "感知与规划", count: 9 }
    ]},
    { id: "sub-4", icon: "🔌", name: "AI嵌入式_机器人开发", desc: "嵌式系统与机器人驱动开发", color: "#eb6834", stages: [
      { id: "st-401", icon: "💾", name: "嵌入式基础", count: 17 },
      { id: "st-402", icon: "⚙️", name: "驱动开发", count: 11 }
    ]},
    { id: "sub-5", icon: "🧪", name: "AI测试", desc: "功能、自动化与 AI 专项测试能力", color: "#e87ba4", stages: [
      { id: "st-501", icon: "📋", name: "测试基础", count: 20 },
      { id: "st-502", icon: "🔁", name: "自动化测试", count: 18 },
      { id: "st-503", icon: "🤖", name: "AI 专项测试", count: 13 }
    ]},
    { id: "sub-6", icon: "☁️", name: "AI运维", desc: "Linux、容器云原生与智能运维", color: "#008300", stages: [
      { id: "st-601", icon: "🐧", name: "Linux 基础", count: 22 },
      { id: "st-602", icon: "📦", name: "容器与 K8s", count: 19 },
      { id: "st-603", icon: "📈", name: "监控与运维", count: 12 }
    ]},
    { id: "sub-7", icon: "🎨", name: "AI视觉设计", desc: "设计基础与 AIGC 绘图创作", color: "#eda100", stages: [
      { id: "st-701", icon: "🖌️", name: "设计基础", count: 15 },
      { id: "st-702", icon: "🖼️", name: "AIGC 绘图", count: 16 }
    ]},
    { id: "sub-8", icon: "🎬", name: "AI视频与短剧创作", desc: "分镜脚本与 AI 视频工具实战", color: "#e34948", stages: [
      { id: "st-801", icon: "📝", name: "分镜与脚本", count: 10 },
      { id: "st-802", icon: "🎥", name: "AI 视频工具", count: 12 }
    ]},
    { id: "sub-9", icon: "📚", name: "其他学科", desc: "兜底分类，暂未规划阶段", color: "#898781", stages: [] }
  ];

  /* ---------- 题目（刷题 / 题库中心共用） ---------- */
  var questions = [
    { id: 1001, subjectId: "sub-1", stageId: "st-101", type: "single", difficulty: "easy",
      title: "下列关于大语言模型（LLM）的描述，正确的是？",
      options: [{ key: "A", text: "LLM 只能处理英文文本" }, { key: "B", text: "LLM 通过海量文本预训练学习语言规律" }, { key: "C", text: "LLM 的参数量越小效果一定越好" }, { key: "D", text: "LLM 不需要任何微调即可用于所有场景" }],
      answer: "B", analysis: "大语言模型通过在海量文本语料上进行预训练，学习语言的统计规律与知识表示，再通过微调、提示工程适配下游任务。",
      tags: ["大模型", "基础概念"], done: 1286, accuracy: 82 },
    { id: 1002, subjectId: "sub-1", stageId: "st-102", type: "single", difficulty: "medium",
      title: "在 Prompt 工程中，「Few-shot」指的是？",
      options: [{ key: "A", text: "不给模型任何示例" }, { key: "B", text: "在提示词中给出少量输入输出示例" }, { key: "C", text: "对模型进行全参数微调" }, { key: "D", text: "限制模型输出长度" }],
      answer: "B", analysis: "Few-shot（少样本提示）是在提示词中给出少量示例，引导模型按示例的模式完成任务；零示例称为 Zero-shot。",
      tags: ["Prompt", "Few-shot"], done: 964, accuracy: 71 },
    { id: 1003, subjectId: "sub-1", stageId: "st-103", type: "multi", difficulty: "medium",
      title: "以下哪些属于 AI Agent 的核心组成部分？（多选）",
      options: [{ key: "A", text: "规划（Planning）" }, { key: "B", text: "记忆（Memory）" }, { key: "C", text: "工具使用（Tool Use）" }, { key: "D", text: "硬盘分区" }],
      answer: "ABC", analysis: "AI Agent 通常由规划、记忆、工具使用与大模型核心四部分组成，硬盘分区属于操作系统概念。",
      tags: ["Agent"], done: 733, accuracy: 64 },
    { id: 1004, subjectId: "sub-1", stageId: "st-101", type: "judge", difficulty: "easy",
      title: "Token 是大模型处理文本的最小单位，一个汉字一定只对应一个 Token。",
      options: [{ key: "T", text: "正确" }, { key: "F", text: "错误" }],
      answer: "F", analysis: "Token 切分取决于分词器（Tokenizer）与具体语料，一个汉字可能对应一个或多个 Token，也可能多个汉字共用 Token。",
      tags: ["Token"], done: 1102, accuracy: 58 },
    { id: 1005, subjectId: "sub-1", stageId: "st-104", type: "short", difficulty: "hard",
      title: "请简述 RAG（检索增强生成）的原理，并说明它解决了大模型的哪些问题。",
      options: [], answer: "",
      analysis: "RAG 将外部知识库检索与大模型生成结合：先根据用户问题检索相关文档片段，再将片段作为上下文注入提示词由模型生成答案。",
      refAnswer: "RAG（检索增强生成）在生成前先从外部知识库中检索与问题相关的文档片段，将其作为上下文注入 Prompt，再由大模型生成答案。它解决了：① 知识截止日期问题（可接入实时更新的资料）；② 幻觉问题（生成有据可依）；③ 领域私有知识缺失（无需重新训练即可使用企业内部资料）。",
      aiGrade: { score: 8, comment: "回答结构清晰，覆盖了检索-注入-生成的核心链路，对解决的问题归纳到位；如能补充「向量检索 + 重排序」的工程细节会更完整。", keyPoints: ["检索外部知识库", "片段注入上下文", "缓解幻觉与知识过时"] },
      tags: ["RAG", "项目实战"], done: 412, accuracy: 47 },
    { id: 1006, subjectId: "sub-2", stageId: "st-201", type: "single", difficulty: "easy",
      title: "神经网络中，激活函数的主要作用是？",
      options: [{ key: "A", text: "引入非线性表达能力" }, { key: "B", text: "加快数据读取" }, { key: "C", text: "压缩模型体积" }, { key: "D", text: "初始化权重" }],
      answer: "A", analysis: "没有激活函数的多层网络等价于单层线性变换，激活函数引入非线性，使网络可以拟合复杂函数。",
      tags: ["深度学习"], done: 1523, accuracy: 88 },
    { id: 1007, subjectId: "sub-2", stageId: "st-202", type: "multi", difficulty: "hard",
      title: "大模型参数高效微调（PEFT）的常见方法有哪些？（多选）",
      options: [{ key: "A", text: "LoRA" }, { key: "B", text: "Prompt Tuning" }, { key: "C", text: "全参数预训练" }, { key: "D", text: "Adapter" }],
      answer: "ABD", analysis: "LoRA、Prompt Tuning、Adapter 都只训练少量新增参数，属于参数高效微调；全参数预训练不属于微调手段且成本极高。",
      tags: ["微调", "LoRA"], done: 645, accuracy: 52 },
    { id: 1008, subjectId: "sub-2", stageId: "st-203", type: "judge", difficulty: "medium",
      title: "模型量化（INT8/INT4）可以在基本保持效果的同时显著降低推理显存占用。",
      options: [{ key: "T", text: "正确" }, { key: "F", text: "错误" }],
      answer: "T", analysis: "量化将权重与激活从高精度浮点映射到低比特整数，显著降低显存与算力需求，配合校准通常效果损失很小。",
      tags: ["量化", "部署"], done: 588, accuracy: 76 },
    { id: 1009, subjectId: "sub-3", stageId: "st-301", type: "single", difficulty: "medium",
      title: "机器人运动学中，正运动学（Forward Kinematics）解决的问题是？",
      options: [{ key: "A", text: "由关节角度求末端执行器位姿" }, { key: "B", text: "由末端位姿求关节角度" }, { key: "C", text: "求机器人质量" }, { key: "D", text: "规划避障路径" }],
      answer: "A", analysis: "正运动学由各关节角度推算末端执行器的位置与姿态；反运动学（IK）则相反，由目标位姿反解关节角度。",
      tags: ["运动学"], done: 356, accuracy: 61 },
    { id: 1010, subjectId: "sub-5", stageId: "st-501", type: "single", difficulty: "easy",
      title: "软件测试中，「黑盒测试」关注的是？",
      options: [{ key: "A", text: "程序内部逻辑结构" }, { key: "B", text: "输入与输出的对应关系" }, { key: "C", text: "代码行覆盖率" }, { key: "D", text: "变量命名规范" }],
      answer: "B", analysis: "黑盒测试不关心内部实现，只依据需求验证输入与输出是否符合预期，常见方法有等价类划分、边界值分析等。",
      tags: ["测试基础"], done: 921, accuracy: 84 },
    { id: 1011, subjectId: "sub-5", stageId: "st-503", type: "multi", difficulty: "medium",
      title: "针对大模型应用的测试重点包括哪些？（多选）",
      options: [{ key: "A", text: "输出事实一致性（幻觉检测）" }, { key: "B", text: "提示词注入等安全风险" }, { key: "C", text: "响应延迟与稳定性" }, { key: "D", text: "界面像素对齐" }],
      answer: "ABC", analysis: "大模型应用测试重点关注输出质量（幻觉、一致性）、安全（提示注入、越狱）与非功能指标（延迟、稳定性），像素对齐属于 UI 还原范畴。",
      tags: ["AI测试"], done: 287, accuracy: 55 },
    { id: 1012, subjectId: "sub-6", stageId: "st-601", type: "single", difficulty: "easy",
      title: "Linux 中，用于查看当前工作目录的命令是？",
      options: [{ key: "A", text: "pwd" }, { key: "B", text: "ls" }, { key: "C", text: "cd" }, { key: "D", text: "top" }],
      answer: "A", analysis: "pwd（print working directory）打印当前工作目录；ls 列出目录内容；cd 切换目录；top 查看进程。",
      tags: ["Linux"], done: 1876, accuracy: 91 },
    { id: 1013, subjectId: "sub-6", stageId: "st-602", type: "judge", difficulty: "medium",
      title: "Kubernetes 中，Deployment 会自动维持期望的 Pod 副本数。",
      options: [{ key: "T", text: "正确" }, { key: "F", text: "错误" }],
      answer: "T", analysis: "Deployment 通过 ReplicaSet 维持期望副本数，Pod 异常退出或节点故障时自动重建。",
      tags: ["K8s"], done: 754, accuracy: 79 },
    { id: 1014, subjectId: "sub-7", stageId: "st-702", type: "short", difficulty: "medium",
      title: "请简述 AIGC 绘图中「提示词（Prompt）」的常用结构，并举例说明。",
      options: [], answer: "",
      analysis: "常用结构为：主体 + 风格 + 细节修饰 + 负向提示 + 参数（比例、采样器等）。",
      refAnswer: "常用 Prompt 结构：① 主体（画面内容，如「一位宇航员」）；② 风格（如「赛博朋克插画风」）；③ 细节修饰（光影、构图、色彩）；④ 负向提示（排除元素，如「模糊、变形」）；⑤ 参数（画幅比例、采样步数）。示例：「一位宇航员站在火星地表，赛博朋克插画风，逆光剪影，8k 细节，--ar 16:9」。",
      aiGrade: { score: 7, comment: "结构归纳基本完整，示例恰当；建议补充负向提示的作用，并提及不同模型对提示词语法的差异。", keyPoints: ["主体+风格+修饰", "负向提示", "参数设置"] },
      tags: ["AIGC", "绘图"], done: 231, accuracy: 63 },
    { id: 1015, subjectId: "sub-1", stageId: "st-102", type: "single", difficulty: "hard",
      title: "为减少大模型幻觉，下列提示词策略中最有效的是？",
      options: [{ key: "A", text: "要求模型「不知道就说不知道」并提供依据来源" }, { key: "B", text: "让模型每次输出越长越好" }, { key: "C", text: "删除所有系统提示" }, { key: "D", text: "随机化温度参数到 2.0" }],
      answer: "A", analysis: "在提示词中明确「不确定时承认不知道、给出依据」能显著抑制幻觉；输出更长反而可能增加编造，温度过高会降低稳定性。",
      tags: ["幻觉", "Prompt"], done: 690, accuracy: 44 },
    { id: 1016, subjectId: "sub-1", stageId: "st-103", type: "single", difficulty: "medium",
      title: "ReAct 框架中，Agent 的一次典型循环是？",
      options: [{ key: "A", text: "思考 → 行动 → 观察" }, { key: "B", text: "输入 → 输出" }, { key: "C", text: "训练 → 评估" }, { key: "D", text: "编码 → 部署" }],
      answer: "A", analysis: "ReAct 将推理（Reasoning）与行动（Acting）交替进行：先思考下一步，再调用工具行动，然后观察结果，循环直至完成任务。",
      tags: ["Agent", "ReAct"], done: 512, accuracy: 67 }
  ];

  /* 题库管理端补充状态字段（管理端表格用） */
  questions.forEach(function (q, i) {
    q.status = [ "online", "online", "pending", "online", "draft", "online", "offline", "online", "online", "online", "pending", "online", "online", "online", "rejected", "online" ][i % 16];
    q.createdAt = "2026-1" + (i % 3 === 0 ? "1" : "0") + "-" + String((i * 3) % 27 + 1).padStart(2, "0") + " 10:" + String((i * 7) % 60).padStart(2, "0");
  });

  /* ---------- B站课程库 ---------- */
  var courses = [
    { id: "c-1", title: "大模型应用开发实战：从 Prompt 到 Agent", bv: "BV1xK4y1E7qA", duration: "6:30", durationMin: 390, subjectIds: ["sub-1"], source: "B站", cover: "🤖", url: "https://www.bilibili.com/" },
    { id: "c-2", title: "LangChain 与 RAG 项目实战教程", bv: "BV1dS4y1m7cR", duration: "4:15", durationMin: 255, subjectIds: ["sub-1", "sub-2"], source: "B站", cover: "🔗", url: "https://www.bilibili.com/" },
    { id: "c-3", title: "深度学习入门：神经网络基础", bv: "BV1aT411N7mV", duration: "8:00", durationMin: 480, subjectIds: ["sub-2"], source: "B站", cover: "🧬", url: "https://www.bilibili.com/" },
    { id: "c-4", title: "大模型微调实战（LoRA / QLoRA）", bv: "BV1hJ411x7pQ", duration: "3:45", durationMin: 225, subjectIds: ["sub-2"], source: "B站", cover: "🔧", url: "https://www.bilibili.com/" },
    { id: "c-5", title: "ROS2 机器人开发从入门到实践", bv: "BV1mC4y1P7kL", duration: "5:20", durationMin: 320, subjectIds: ["sub-3"], source: "B站", cover: "🦾", url: "https://www.bilibili.com/" },
    { id: "c-6", title: "嵌入式 Linux 驱动开发精讲", bv: "BV1rN4y1T7bW", duration: "7:10", durationMin: 430, subjectIds: ["sub-4"], source: "B站", cover: "🔌", url: "https://www.bilibili.com/" },
    { id: "c-7", title: "软件测试全流程：从用例设计到自动化", bv: "BV1sY4y1k7dM", duration: "5:50", durationMin: 350, subjectIds: ["sub-5"], source: "B站", cover: "🧪", url: "https://www.bilibili.com/" },
    { id: "c-8", title: "Docker 与 Kubernetes 实战", bv: "BV1pQ4y1v7cX", duration: "6:05", durationMin: 365, subjectIds: ["sub-6"], source: "B站", cover: "☁️", url: "https://www.bilibili.com/" },
    { id: "c-9", title: "Prometheus 智能监控体系搭建", bv: "BV1wE4y1r7tY", duration: "2:40", durationMin: 160, subjectIds: ["sub-6"], source: "B站", cover: "📈", url: "https://www.bilibili.com/" },
    { id: "c-10", title: "AIGC 绘图：Midjourney 与 Stable Diffusion", bv: "BV1uI4y1o7uZ", duration: "4:00", durationMin: 240, subjectIds: ["sub-7"], source: "B站", cover: "🎨", url: "https://www.bilibili.com/" },
    { id: "c-11", title: "AI 短剧创作：分镜脚本与成片实战", bv: "BV1yH4y1i7oP", duration: "3:20", durationMin: 200, subjectIds: ["sub-8"], source: "B站", cover: "🎬", url: "https://www.bilibili.com/" },
    { id: "c-12", title: "Agent 开发进阶：多智能体协作", bv: "BV1zM4y1a7sD", duration: "2:55", durationMin: 175, subjectIds: ["sub-1"], source: "B站", cover: "🤖", url: "https://www.bilibili.com/" },
    { id: "c-13", title: "面试高频算法题精讲（内部资料）", bv: "", duration: "1:30", durationMin: 90, subjectIds: ["sub-9"], source: "其他", cover: "📘", url: "" },
    { id: "c-14", title: "大模型推理加速：vLLM 部署实践", bv: "BV1gF4y1e7qS", duration: "2:15", durationMin: 135, subjectIds: ["sub-2", "sub-1"], source: "B站", cover: "⚡", url: "https://www.bilibili.com/" }
  ];

  /* ---------- 学习路线 ---------- */
  var routes = [
    { id: "r-1", name: "AI 应用开发入门路线", subjectId: "sub-1", icon: "🚀", status: "enabled",
      audience: "零基础转行 AI 应用开发的学员", desc: "从大模型基础概念到 Agent 项目实战，循序渐进建立 AI 应用开发完整知识体系。",
      courseIds: ["c-1", "c-2", "c-12", "c-14"], learned: ["c-1"], updatedAt: "2026-11-12" },
    { id: "r-2", name: "大模型开发进阶路线", subjectId: "sub-2", icon: "🧬", status: "enabled",
      audience: "有深度学习基础、想做大模型研发的学员", desc: "覆盖深度学习基础、参数高效微调与推理部署三大能力模块。",
      courseIds: ["c-3", "c-4", "c-14"], learned: [], updatedAt: "2026-11-08" },
    { id: "r-3", name: "AI 运维云原生路线", subjectId: "sub-6", icon: "☁️", status: "enabled",
      audience: "运维工程师转型智能运维", desc: "容器化、Kubernetes 与监控体系一条龙。",
      courseIds: ["c-8", "c-9"], learned: ["c-8", "c-9"], updatedAt: "2026-10-30" },
    { id: "r-4", name: "AI 视觉设计创作路线", subjectId: "sub-7", icon: "🎨", status: "enabled",
      audience: "设计爱好者与转行人群", desc: "设计基础 + AIGC 绘图工具双引擎。",
      courseIds: ["c-10"], learned: [], updatedAt: "2026-11-15" },
    { id: "r-5", name: "测试开发进阶路线", subjectId: "sub-5", icon: "🧪", status: "disabled",
      audience: "初中级测试工程师", desc: "从测试基础到自动化与 AI 专项测试（路线筹备中）。",
      courseIds: ["c-7"], learned: [], updatedAt: "2026-11-01" }
  ];

  /* ---------- 错题本 ---------- */
  var wrongList = [
    { id: "w-1", qid: 1015, type: "single", title: "为减少大模型幻觉，下列提示词策略中最有效的是？", category: "AI应用与智能体开发 / Prompt 工程",
      wrongCount: 4, corrected: 0, mastered: false, lastWrong: "2026-11-18", myAnswer: "B", rightAnswer: "A",
      hasOptions: true,
      options: [{ key: "A", text: "要求模型「不知道就说不知道」并给出依据来源" }, { key: "B", text: "让模型每次输出越长越好" }, { key: "C", text: "删除所有系统提示" }, { key: "D", text: "随机化温度参数到 2.0" }] },
    { id: "w-2", qid: 1003, type: "multi", title: "以下哪些属于 AI Agent 的核心组成部分？", category: "AI应用与智能体开发 / Agent 开发",
      wrongCount: 3, corrected: 1, mastered: false, lastWrong: "2026-11-17", myAnswer: "AB", rightAnswer: "ABC",
      hasOptions: true,
      options: [{ key: "A", text: "规划（Planning）" }, { key: "B", text: "记忆（Memory）" }, { key: "C", text: "工具使用（Tool Use）" }, { key: "D", text: "硬盘分区" }] },
    { id: "w-3", qid: 1007, type: "multi", title: "大模型参数高效微调（PEFT）的常见方法有哪些？", category: "AI大模型开发 / 大模型微调",
      wrongCount: 3, corrected: 0, mastered: false, lastWrong: "2026-11-16", myAnswer: "AC", rightAnswer: "ABD",
      hasOptions: true,
      options: [{ key: "A", text: "LoRA" }, { key: "B", text: "Prompt Tuning" }, { key: "C", text: "全参数预训练" }, { key: "D", text: "Adapter" }] },
    { id: "w-4", qid: 1004, type: "judge", title: "Token 是大模型处理文本的最小单位，一个汉字一定只对应一个 Token。", category: "AI应用与智能体开发 / 大模型基础",
      wrongCount: 2, corrected: 2, mastered: false, lastWrong: "2026-11-15", myAnswer: "正确", rightAnswer: "错误",
      hasOptions: true,
      options: [{ key: "T", text: "正确" }, { key: "F", text: "错误" }] },
    { id: "w-5", qid: 1009, type: "single", title: "机器人运动学中，正运动学（Forward Kinematics）解决的问题是？", category: "AI具身智能机器人开发 / 机器人学基础",
      wrongCount: 2, corrected: 3, mastered: true, lastWrong: "2026-11-10", myAnswer: "B", rightAnswer: "A",
      hasOptions: true,
      options: [{ key: "A", text: "由关节角度求末端执行器位姿" }, { key: "B", text: "由末端位姿求关节角度" }, { key: "C", text: "求机器人质量" }, { key: "D", text: "规划避障路径" }] },
    { id: "w-6", qid: null, type: "short", title: "请简述 RAG 的原理，并说明它解决了大模型的哪些问题。", category: "AI应用与智能体开发 / 项目实战",
      wrongCount: 3, corrected: 0, mastered: false, lastWrong: "2026-11-14", myAnswer: "（简答未通过）", rightAnswer: "见参考答案",
      hasOptions: false, options: [] },
    { id: "w-7", qid: 1011, type: "multi", title: "针对大模型应用的测试重点包括哪些？", category: "AI测试 / AI 专项测试",
      wrongCount: 1, corrected: 1, mastered: false, lastWrong: "2026-11-12", myAnswer: "ABCD", rightAnswer: "ABC",
      hasOptions: true,
      options: [{ key: "A", text: "输出事实一致性（幻觉检测）" }, { key: "B", text: "提示词注入等安全风险" }, { key: "C", text: "响应延迟与稳定性" }, { key: "D", text: "界面像素对齐" }] },
    { id: "w-8", qid: 1013, type: "judge", title: "Kubernetes 中，Deployment 会自动维持期望的 Pod 副本数。", category: "AI运维 / 容器与 K8s",
      wrongCount: 1, corrected: 2, mastered: false, lastWrong: "2026-11-08", myAnswer: "错误", rightAnswer: "正确",
      hasOptions: true,
      options: [{ key: "T", text: "正确" }, { key: "F", text: "错误" }] }
  ];

  /* ---------- AI 面试：脚本化问答（模拟 AI 面试官） ---------- */
  var interviewScript = [
    { q: "请先做一个简短的自我介绍，并说明你为什么选择 AI 应用与智能体开发方向？",
      feedback: { score: 8, comment: "自我介绍结构完整，动机阐述清晰，能结合自身经历说明选择该方向的原因。建议在介绍中补充 1-2 个可量化的项目成果，会更有说服力。",
        keypoints: ["结构完整", "动机清晰", "可补充量化成果"] } },
    { q: "请解释一下什么是 RAG（检索增强生成）？它在企业知识库问答场景中如何落地？",
      feedback: { score: 7, comment: "对 RAG 的基本原理回答正确，提到了向量检索与文档切分。对企业落地中的权限过滤、重排序与引用溯源还可以展开得更具体。",
        keypoints: ["原理正确", "提到向量检索", "落地细节可展开"] } },
    { q: "如果 Agent 在执行任务时反复调用同一个工具并陷入循环，你会如何排查和解决？",
      feedback: { score: 6, comment: "给出了增加最大步数限制与日志排查的思路，方向正确。建议补充循环检测（重复状态判断）、工具调用结果缓存以及失败降级策略，形成完整方案。",
        keypoints: ["有循环限制意识", "会查日志", "缺循环检测与降级"] } },
    { q: "请介绍一个你做过的最有挑战的 AI 项目，你承担了什么角色？遇到的最大困难是什么？",
      feedback: { score: 9, comment: "项目描述具体，角色分工明确，能清晰呈现问题定位到解决的完整链路，STAR 结构运用得当，是很强的一段回答。",
        keypoints: ["STAR 结构", "难点剖析到位", "结果可量化"] } },
    { q: "最后一个问题：你认为大模型应用工程师在未来两年最需要补齐的能力是什么？为什么？",
      feedback: { score: 8, comment: "观点明确，能从工程化与评估体系两个角度展开，逻辑自洽。若能结合具体技术趋势（如多模态、Agent 标准化）举例会更出彩。",
        keypoints: ["观点明确", "逻辑自洽", "可结合趋势举例"] } }
  ];

  /* ---------- 面试题库（管理端） ---------- */
  var interviewBank = [
    { id: "iq-1", direction: "AI应用与智能体开发", stem: "请解释什么是 RAG，它解决了大模型的哪些问题？", refAnswer: "RAG 通过检索外部知识库并注入上下文，缓解幻觉、知识过时与私有知识缺失问题。", topic: "RAG", difficulty: "medium", tags: "RAG,检索", source: { type: "manual" } },
    { id: "iq-2", direction: "AI应用与智能体开发", stem: "ReAct 框架的核心思想是什么？", refAnswer: "推理与行动交替循环：思考-行动-观察，直至任务完成。", topic: "Agent", difficulty: "easy", tags: "Agent,ReAct", source: { type: "manual" } },
    { id: "iq-3", direction: "AI大模型开发", stem: "请比较 LoRA 与全参数微调的优缺点。", refAnswer: "LoRA 训练参数少、显存低、易切换；全参数微调效果上限高但成本大。", topic: "微调", difficulty: "medium", tags: "LoRA,PEFT", source: { type: "excel", file: "大模型面试题-批量.xlsx", row: 12 } },
    { id: "iq-4", direction: "AI大模型开发", stem: "什么是模型量化？INT8 量化的原理是什么？", refAnswer: "将高精度权重映射为低比特整数，降低显存与算力需求。", topic: "部署", difficulty: "medium", tags: "量化,部署", source: { type: "excel", file: "大模型面试题-批量.xlsx", row: 18 } },
    { id: "iq-5", direction: "AI测试", stem: "如何设计大模型应用的幻觉检测用例？", refAnswer: "构造有标准答案的事实类问题集，比对输出与知识库引用，统计一致率。", topic: "AI测试", difficulty: "hard", tags: "幻觉,测试", source: { type: "manual" } },
    { id: "iq-6", direction: "AI运维", stem: "Kubernetes 中 liveness 与 readiness 探针的区别？", refAnswer: "liveness 决定是否重启容器，readiness 决定是否接流量。", topic: "K8s", difficulty: "easy", tags: "K8s,探针", source: { type: "manual" } },
    { id: "iq-7", direction: "AI应用与智能体开发", stem: "提示词注入攻击是什么？如何防御？", refAnswer: "通过构造输入劫持模型行为；防御包括输入清洗、权限隔离、输出过滤与系统提示加固。", topic: "安全", difficulty: "hard", tags: "安全,提示注入", source: { type: "excel", file: "安全面试题.xlsx", row: 3 } },
    { id: "iq-8", direction: "AI视觉设计", stem: "AIGC 绘图中如何提升出图可控性？", refAnswer: "结构化提示词、ControlNet 控制、种子固定与图生图迭代。", topic: "AIGC绘图", difficulty: "medium", tags: "AIGC,绘图", source: { type: "manual" } },
    { id: "iq-9", direction: "AI嵌入式_机器人开发", stem: "嵌入式系统中中断服务程序的编写要注意什么？", refAnswer: "尽量短小、避免阻塞、使用 volatile、注意临界区保护。", topic: "嵌入式", difficulty: "medium", tags: "嵌入式,中断", source: { type: "manual" } },
    { id: "iq-10", direction: "AI具身智能机器人开发", stem: "机器人 SLAM 的基本流程是什么？", refAnswer: "前端里程计 + 后端优化 + 回环检测，输出全局一致地图与轨迹。", topic: "感知与规划", difficulty: "hard", tags: "SLAM,机器人", source: { type: "excel", file: "机器人面试题.xlsx", row: 7 } },
    { id: "iq-11", direction: "AI视频与短剧创作", stem: "AI 视频生成中如何保持角色一致性？", refAnswer: "角色参考图、固定种子、LoRA 角色模型与分镜统一风格描述。", topic: "AI视频", difficulty: "medium", tags: "视频,一致性", source: { type: "manual" } },
    { id: "iq-12", direction: "AI大模型开发", stem: "请简述 Transformer 中注意力机制的计算过程。", refAnswer: "Q/K/V 线性变换，softmax(QK^T/√d)V 加权求和。", topic: "深度学习", difficulty: "medium", tags: "Transformer,注意力", source: { type: "manual" } }
  ];

  /* ---------- 面试记录 ---------- */
  var interviewRecords = [
    { id: "ir-1", direction: "AI应用与智能体开发", difficulty: "medium", count: 10, durationSec: 1520, score: 82, datetime: "2026-11-18 21:30" },
    { id: "ir-2", direction: "AI应用与智能体开发", difficulty: "medium", count: 5, durationSec: 780, score: 76, datetime: "2026-11-15 20:10" },
    { id: "ir-3", direction: "AI大模型开发", difficulty: "hard", count: 8, durationSec: 1240, score: 68, datetime: "2026-11-12 19:45" },
    { id: "ir-4", direction: "AI应用与智能体开发", difficulty: "easy", count: 3, durationSec: 420, score: 88, datetime: "2026-11-08 22:05" },
    { id: "ir-5", direction: "AI测试", difficulty: "medium", count: 5, durationSec: 690, score: 71, datetime: "2026-11-03 20:55" },
    { id: "ir-6", direction: "AI应用与智能体开发", difficulty: "hard", count: 10, durationSec: 1710, score: 63, datetime: "2026-10-28 21:15" },
    { id: "ir-7", direction: "AI运维", difficulty: "easy", count: 3, durationSec: 380, score: 85, datetime: "2026-10-22 19:30" }
  ];

  /* ---------- 学员（管理端） ---------- */
  var students = [
    { id: "u-1001", name: "林小雨", phone: "13805716721", email: "linxy@example.com", regTime: "2026-08-12", studyDays: 46, practice: 356, interviews: 7, status: "enabled", lastLogin: "2026-11-19 09:12", accuracy: 78, courses: 3 },
    { id: "u-1002", name: "陈一鸣", phone: "13912345678", email: "chenym@example.com", regTime: "2026-09-03", studyDays: 32, practice: 218, interviews: 5, status: "enabled", lastLogin: "2026-11-18 22:40", accuracy: 72, courses: 2 },
    { id: "u-1003", name: "苏晚晴", phone: "13755558888", email: "suwq@example.com", regTime: "2026-09-21", studyDays: 25, practice: 167, interviews: 3, status: "enabled", lastLogin: "2026-11-17 18:05", accuracy: 81, courses: 2 },
    { id: "u-1004", name: "王铁柱", phone: "13666662333", email: "", regTime: "2026-10-02", studyDays: 11, practice: 64, interviews: 1, status: "disabled", lastLogin: "2026-10-28 10:22", accuracy: 55, courses: 1 },
    { id: "u-1005", name: "赵梦琪", phone: "13500001111", email: "zhaomq@example.com", regTime: "2026-10-15", studyDays: 18, practice: 129, interviews: 4, status: "enabled", lastLogin: "2026-11-19 08:47", accuracy: 74, courses: 2 },
    { id: "u-1006", name: "刘星河", phone: "13488886666", email: "liuxh@example.com", regTime: "2026-10-26", studyDays: 9, practice: 41, interviews: 0, status: "enabled", lastLogin: "2026-11-16 21:33", accuracy: 66, courses: 1 },
    { id: "u-1007", name: "孙浩然", phone: "13322223333", email: "sunhr@example.com", regTime: "2026-11-05", studyDays: 5, practice: 23, interviews: 1, status: "enabled", lastLogin: "2026-11-18 20:19", accuracy: 61, courses: 0 },
    { id: "u-1008", name: "周雨桐", phone: "13277779999", email: "zhouyt@example.com", regTime: "2026-11-12", studyDays: 2, practice: 9, interviews: 0, status: "enabled", lastLogin: "2026-11-19 10:02", accuracy: 0, courses: 0 }
  ];

  /* ---------- 后台用户（系统管理） ---------- */
  var adminUsers = [
    { id: "au-1", username: "admin", phone: "13800000001", email: "admin@yunshu.com", role: "超级管理员", status: "enabled", lastLogin: "2026-11-19 08:30", createdAt: "2026-07-01", builtin: true },
    { id: "au-2", username: "reviewer01", phone: "13800000002", email: "rev01@yunshu.com", role: "内容审核", status: "enabled", lastLogin: "2026-11-18 16:22", createdAt: "2026-08-15", builtin: false },
    { id: "au-3", username: "operator01", phone: "13800000003", email: "op01@yunshu.com", role: "运营人员", status: "enabled", lastLogin: "2026-11-19 09:50", createdAt: "2026-08-15", builtin: false },
    { id: "au-4", username: "operator02", phone: "13800000004", email: "", role: "运营人员", status: "disabled", lastLogin: "2026-10-20 14:11", createdAt: "2026-09-10", builtin: false },
    { id: "au-5", username: "reviewer02", phone: "13800000005", email: "rev02@yunshu.com", role: "内容审核", status: "enabled", lastLogin: "2026-11-17 11:08", createdAt: "2026-09-28", builtin: false }
  ];

  /* ---------- 角色与权限树（9 组 33 项） ---------- */
  var permTree = [
    { group: "题库管理", perms: ["查看", "新增", "编辑", "删除", "导入", "导出", "审核"] },
    { group: "面试题库管理", perms: ["查看", "编辑", "删除", "检索测试"] },
    { group: "用户管理", perms: ["查看", "新增", "编辑", "禁用"] },
    { group: "学习路线", perms: ["查看", "新增", "编辑", "删除"] },
    { group: "学员管理", perms: ["查看", "编辑", "删除"] },
    { group: "学科管理", perms: ["查看", "新增", "编辑", "删除"] },
    { group: "课程库", perms: ["查看", "新增", "编辑", "删除"] },
    { group: "数据看板", perms: ["查看"] },
    { group: "系统管理", perms: ["日志查看", "系统设置"] }
  ];
  var roles = [
    { id: "role-1", name: "超级管理员", code: "super_admin", userCount: 1, desc: "系统内置角色，拥有全部权限", all: true, perms: [] },
    { id: "role-2", name: "内容审核", code: "content_reviewer", userCount: 2, desc: "只把关不生产：查看全部内容并审核题目，无增删改权限", all: false,
      perms: ["题库管理·查看", "题库管理·审核", "面试题库管理·查看", "课程库·查看", "学科管理·查看", "学习路线·查看", "数据看板·查看"] },
    { id: "role-3", name: "运营人员", code: "operator", userCount: 2, desc: "除系统管理、用户管理外的全部操作，含内容维护与学员管理", all: false,
      perms: ["题库管理·查看", "题库管理·新增", "题库管理·编辑", "题库管理·删除", "题库管理·导入", "题库管理·导出", "面试题库管理·查看", "面试题库管理·编辑", "学习路线·查看", "学习路线·新增", "学习路线·编辑", "学员管理·查看", "学员管理·编辑", "学科管理·查看", "学科管理·新增", "学科管理·编辑", "课程库·查看", "课程库·新增", "课程库·编辑", "数据看板·查看"] }
  ];

  /* ---------- 操作日志 ---------- */
  var logs = [
    { id: "log-1", user: "operator01", action: "新增课程", target: "课程《大模型推理加速：vLLM 部署实践》", ip: "192.168.1.24", time: "2026-11-19 10:21", type: "create" },
    { id: "log-2", user: "admin", action: "登录", target: "管理后台", ip: "192.168.1.8", time: "2026-11-19 08:30", type: "login" },
    { id: "log-3", user: "reviewer01", action: "审核通过", target: "题目 #1003", ip: "192.168.1.31", time: "2026-11-18 17:45", type: "other" },
    { id: "log-4", user: "operator01", action: "编辑学习路线", target: "《AI 应用开发入门路线》", ip: "192.168.1.24", time: "2026-11-18 16:02", type: "update" },
    { id: "log-5", user: "operator02", action: "禁用学员", target: "学员 王铁柱", ip: "192.168.1.45", time: "2026-11-18 11:30", type: "toggle" },
    { id: "log-6", user: "admin", action: "重置密码", target: "用户 operator02", ip: "192.168.1.8", time: "2026-11-17 15:12", type: "other" },
    { id: "log-7", user: "operator01", action: "批量导入题目", target: "题库 Excel（120 道）", ip: "192.168.1.24", time: "2026-11-17 10:40", type: "create" },
    { id: "log-8", user: "reviewer02", action: "审核不通过", target: "题目 #1015", ip: "192.168.1.36", time: "2026-11-16 18:22", type: "other" },
    { id: "log-9", user: "operator01", action: "删除课程", target: "课程《旧版教程》", ip: "192.168.1.24", time: "2026-11-16 14:55", type: "delete" },
    { id: "log-10", user: "admin", action: "系统设置", target: "修改平台名称", ip: "192.168.1.8", time: "2026-11-15 09:18", type: "update" },
    { id: "log-11", user: "operator02", action: "导出学员", target: "学员列表（8 条）", ip: "192.168.1.45", time: "2026-11-14 16:40", type: "other" },
    { id: "log-12", user: "reviewer01", action: "登录", target: "管理后台", ip: "192.168.1.31", time: "2026-11-14 09:02", type: "login" },
    { id: "log-13", user: "operator01", action: "新增学科", target: "学科《AI视频与短剧创作》", ip: "192.168.1.24", time: "2026-11-13 15:26", type: "create" },
    { id: "log-14", user: "admin", action: "新增用户", target: "用户 reviewer02", ip: "192.168.1.8", time: "2026-11-12 11:11", type: "create" },
    { id: "log-15", user: "operator01", action: "上架题目", target: "题目 #1012", ip: "192.168.1.24", time: "2026-11-11 10:35", type: "toggle" },
    { id: "log-16", user: "admin", action: "清空日志", target: "历史日志（32 条）", ip: "192.168.1.8", time: "2026-11-10 08:59", type: "delete" }
  ];
  var logTypeLabel = { login: "登录", create: "新增·创建·上传", update: "修改·编辑", delete: "删除", toggle: "禁用·启用", other: "其他" };

  /* ---------- 图表数据 ---------- */
  var weekPractice = [
    { day: "周四", n: 18 }, { day: "周五", n: 24 }, { day: "周六", n: 12 },
    { day: "周日", n: 30 }, { day: "周一", n: 26 }, { day: "周二", n: 21 }, { day: "今天", n: 23 }
  ];
  // 用户增长（确定性伪随机，7/30/90 天）
  function genGrowth(n) {
    var arr = [], base = 1200, seed = n;
    for (var i = 0; i < n; i++) {
      seed = (seed * 9301 + 49297) % 233280;
      var wave = Math.sin(i / 6) * 40;
      base += Math.round(seed / 233280 * 26) + (i % 7 === 5 || i % 7 === 6 ? -6 : 8);
      arr.push({ label: (i + 1) + "天前", value: Math.round(base + wave) });
    }
    return arr;
  }
  var userGrowth = { 7: genGrowth(7), 30: genGrowth(30), 90: genGrowth(90) };
  var subjectDist = subjects.slice(0, 8).map(function (s) {
    return { name: s.name.length > 6 ? s.name.slice(0, 5) + "…" : s.name, fullName: s.name, count: s.stages.reduce(function (a, b) { return a + b.count; }, 0) };
  });

  /* ---------- 首页 / 学习统计 ---------- */
  var heroStats = [
    { num: 5200, suffix: "+", label: "精选面试题" },
    { num: 23000, suffix: "+", label: "注册学员" },
    { num: 96000, suffix: "+", label: "AI面试次数" },
    { num: 98, suffix: "%", label: "好评率" }
  ];
  var learnStats = { streak: 12, accuracy: 78, totalPracticed: 356, todayDone: 23 };

  /* ---------- 面试配置 ---------- */
  var ivDirections = [
    { id: "d1", name: "AI应用与智能体开发", desc: "大模型应用、Agent 开发", default: true },
    { id: "d2", name: "AI大模型开发", desc: "微调、推理与部署" },
    { id: "d3", name: "AI具身智能机器人开发", desc: "感知、控制与规划" },
    { id: "d4", name: "AI嵌入式_机器人开发", desc: "嵌入式与驱动开发" },
    { id: "d5", name: "AI测试", desc: "功能、自动化与 AI 专项测试" },
    { id: "d6", name: "AI运维", desc: "云原生与智能运维" },
    { id: "d7", name: "AI视觉设计", desc: "设计基础与 AIGC 绘图" },
    { id: "d8", name: "AI视频与短剧创作", desc: "分镜脚本与 AI 视频" }
  ];
  var ivDifficulties = [
    { id: "easy", name: "简单", desc: "基础面试 · 适合初学者热身" },
    { id: "medium", name: "中等", desc: "进阶面试 · 适合有一定项目经验者", default: true },
    { id: "hard", name: "困难", desc: "高级面试 · 适合冲刺高薪岗位" }
  ];
  var ivQuota = { used: 2, total: 5 };

  /* ---------- 通知（管理端铃铛） ---------- */
  var notices = [
    { id: "n-1", text: "题目 #1003 已通过审核并上架", time: "10 分钟前", unread: true },
    { id: "n-2", text: "《大模型面试题-批量.xlsx》导入完成（8 题）", time: "1 小时前", unread: true },
    { id: "n-3", text: "学员 周雨桐 完成注册", time: "今天 10:02", unread: true },
    { id: "n-4", text: "系统备份完成", time: "昨天 23:00", unread: false }
  ];

  /* ---------- 系统设置 ---------- */
  var settings = { name: "云枢智学", desc: "AI 赋能的智能面试训练平台：刷题 → 错题 → AI 面试 → 报告 → 补强，一站式求职训练闭环。", logo: "", avatar: "" };

  return {
    typeLabel: typeLabel, diffLabel: diffLabel, qStatus: qStatus, logTypeLabel: logTypeLabel,
    user: user, admin: admin,
    subjects: subjects, questions: questions, courses: courses, routes: routes, wrongList: wrongList,
    interviewScript: interviewScript, interviewBank: interviewBank, interviewRecords: interviewRecords,
    students: students, adminUsers: adminUsers, roles: roles, permTree: permTree, logs: logs,
    weekPractice: weekPractice, userGrowth: userGrowth, subjectDist: subjectDist,
    heroStats: heroStats, learnStats: learnStats,
    ivDirections: ivDirections, ivDifficulties: ivDifficulties, ivQuota: ivQuota,
    notices: notices, settings: settings
  };
})();
