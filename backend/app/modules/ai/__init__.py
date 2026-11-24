"""ai · AI 能力层（02 §3.1 / D5）。

职责：LLM 统一封装——简答批改、面试出题、逐题评分、报告生成、补强建议文案；
输出结构化 JSON 校验 + 失败重试 + 评分限幅（0-10）。

约定（02 §3.3）：AI 能力只从本模块出，learning/interview 不直接调用 LLM SDK；
供应商可配置切换（AI_PROVIDER），联调期 Mock Provider，供应商后补仅新增实现。
"""
