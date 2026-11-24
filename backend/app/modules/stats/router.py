"""stats 路由（portal /home/*、/profile/stats 与 admin /dashboard* 双侧挂载）。"""
from fastapi import APIRouter

router = APIRouter(tags=["stats"])
