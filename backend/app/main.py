"""应用入口：路由注册、中间件装配、异常处理、生命周期（02 §4.2）。

运行（开发）：uvicorn app.main:app --reload --port 8000
接口文档：http://localhost:8000/docs（FastAPI OpenAPI，对齐 api-rules）
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.portal import router as portal_router
from app.common import error_codes  # noqa: F401  （错误码常量集中定义）
from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.exceptions import register_exception_handlers
from app.core.redis import close_redis, get_redis

API_PREFIX_PORTAL = "/api/portal/v1"
API_PREFIX_ADMIN = "/api/admin/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    register_exception_handlers(app)

    if settings.debug:
        # 开发期放行前端 dev server（5173/5174）；生产由 Nginx 同源接入（02 §1.3.5）
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173", "http://localhost:5174"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(portal_router, prefix=API_PREFIX_PORTAL)
    app.include_router(admin_router, prefix=API_PREFIX_ADMIN)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict:
        """运维探活：检查 MySQL / Redis 连通性（不含业务逻辑）。"""
        status: dict = {"status": "ok", "mysql": "ok", "redis": "ok"}
        try:
            async with SessionLocal() as session:
                from sqlalchemy import text

                await session.execute(text("SELECT 1"))
        except Exception:
            status["mysql"] = "down"
            status["status"] = "degraded"
        try:
            await get_redis().ping()
        except Exception:
            status["redis"] = "down"
            status["status"] = "degraded"
        return status

    return app


app = create_app()
