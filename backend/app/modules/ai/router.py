"""ai 模块无对外路由（被 learning/interview 经 service 调用，02 §3.3）。"""
from fastapi import APIRouter

router = APIRouter(tags=["ai"])  # 空路由，保持模块结构一致
