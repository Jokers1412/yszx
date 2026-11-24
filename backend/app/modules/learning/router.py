"""learning 路由（挂载于 /api/portal/v1）。

接口清单见 04 §2.1：
  /stages/{id}/questions | /questions/{id}
  POST /practice/paper | /practice/answers
  /wrong-questions*（统计卡/列表/重做/批量）
  /routes* | POST /courses/{id}/complete
待功能开发阶段按契约实现。
"""
from fastapi import APIRouter

router = APIRouter(tags=["learning"])
