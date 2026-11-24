"""students 路由（挂载于 /api/admin/v1）。接口清单见 04 §2.2 /students*。"""
from fastapi import APIRouter

router = APIRouter(tags=["students"])
