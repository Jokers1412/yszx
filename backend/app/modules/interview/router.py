"""interview 路由（挂载于 /api/portal/v1）。

接口清单见 04 §2.1（/interviews* 共 7 个）：
  发起面试（配额校验+抽题）| 提交作答（逐题评分）| finish | 报告 | 记录列表/详情/回放
待功能开发阶段按契约实现。
"""
from fastapi import APIRouter

router = APIRouter(tags=["interview"])
