"""岗位能力知识图谱 — 纯 API 后端。

前后端分离设计：
    - 本服务 (:8000) 仅提供 REST API，不渲染任何 HTML
    - 前端由独立的 Web 服务器托管（开发：Vite :5173，生产：nginx/CDN）
    - 前端通过 /api 前缀代理到本服务
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化后台服务，关闭时清理资源。"""
    # 启动采集调度器
    try:
        from collector.scheduler import get_scheduler
        scheduler = get_scheduler()
        scheduler.add_job("tencent", "Java", "深圳", interval_hours=24)
        scheduler.add_job("tencent", "Python", "北京", interval_hours=24)
        scheduler.start()
        logger.info("采集调度器已启动")
    except Exception as exc:
        logger.warning(f"采集调度器启动失败: {exc}")

    yield

    # 关闭资源
    try:
        from collector.scheduler import get_scheduler
        get_scheduler().stop()
        logger.info("采集调度器已停止")
    except Exception as exc:
        logger.warning(f"调度器关闭异常: {exc}")

    try:
        from web.middleware.logging import shutdown_log_buffer
        shutdown_log_buffer()
    except Exception:
        pass


app = FastAPI(
    title="岗位-能力知识图谱 API",
    description="多源异构数据驱动的岗位能力知识图谱全息可视化平台",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS（前后端分离必须） ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 限流中间件（CORS 之后，日志之前） ─────────────────────────────────
from web.middleware.rate_limit import RateLimitMiddleware  # noqa: E402
from web._settings import get_settings  # noqa: E402

_settings = get_settings()
app.add_middleware(
    RateLimitMiddleware,
    default_limit=_settings.rate_limit_global,
)
RateLimitMiddleware.set_endpoint_limit("/api/admin", _settings.rate_limit_admin)
app.state.rate_limit_enabled = _settings.rate_limit_enabled

# ── 请求日志中间件 ─────────────────────────────────────────────────────
from web.middleware.logging import request_logging_middleware  # noqa: E402
app.middleware("http")(request_logging_middleware)


# ── 注册 API 路由 ──────────────────────────────────────────────────────
from web.api_overview import router as overview_router
from web.api_skills import router as skills_router
from web.api_distribution import router as distribution_router
from web.api_salary import router as salary_router
from web.api_matching import router as matching_router
from web.api_evolution import router as evolution_router
from web.api_rag import router as rag_router
from web.api_updater import router as updater_router
from web.api_resume import router as resume_router
from web.api_skill_manage import router as skill_manage_router
from web.api_graph_admin import router as graph_admin_router
from web.api_job_review import router as job_review_router
from web.api_taxonomy import router as taxonomy_router
from web.api_reports import router as reports_router
from web.api_admin import router as admin_router
from web.api_collector import router as collector_router

app.include_router(collector_router)
app.include_router(overview_router)
app.include_router(skills_router)
app.include_router(distribution_router)
app.include_router(salary_router)
app.include_router(matching_router)
app.include_router(evolution_router)
app.include_router(rag_router)
app.include_router(updater_router)
app.include_router(resume_router)
app.include_router(skill_manage_router)
app.include_router(graph_admin_router)
app.include_router(job_review_router)
app.include_router(taxonomy_router)
app.include_router(reports_router)
app.include_router(admin_router)


# ── 全局异常处理 ───────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(
        f"未捕获异常 [request_id={request_id}] {request.method} {request.url.path}"
    )
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "request_id": request_id},
    )


# ── 管理面板（独立 HTML，无需前端框架） ────────────────────────────────
from pathlib import Path
from fastapi.responses import FileResponse

_TEMPLATES = Path(__file__).parent / "templates"


@app.get("/admin")
async def admin_dashboard():
    return FileResponse(_TEMPLATES / "admin.html")


# ── 根路由：API 信息 ───────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "service": "岗位-能力知识图谱 API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/api/admin/health",
        "dashboard": "/admin",
    }
