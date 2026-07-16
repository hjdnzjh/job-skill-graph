"""FastAPI application: route registration, CORS, static file serving."""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

logger = logging.getLogger(__name__)

app = FastAPI(
    title="岗位-能力知识图谱全息可视化平台",
    description="Multi-source heterogeneous data driven job-skill knowledge graph visualization",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware — after CORS, before logging
from web.middleware.rate_limit import RateLimitMiddleware  # noqa: E402
from web._settings import get_settings  # noqa: E402 — imported above but we need it here too

_settings = get_settings()
app.add_middleware(
    RateLimitMiddleware,
    default_limit=_settings.rate_limit_global,
)
# Register per-endpoint admin limit
RateLimitMiddleware.set_endpoint_limit("/api/admin", _settings.rate_limit_admin)
# Make rate-limit toggle available at runtime
app.state.rate_limit_enabled = _settings.rate_limit_enabled

# Register request-logging middleware (after CORS, before routers)
from web.middleware.logging import request_logging_middleware  # noqa: E402
app.middleware("http")(request_logging_middleware)


# Import and register sub-routers
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

# ── Global exception handler (after routers, before static) ──────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(
        f"Unhandled error [request_id={request_id}] {request.method} {request.url.path}"
    )
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "request_id": request_id},
    )


_STATIC_DIR = Path(__file__).parent / "static"
_DIST_DIR = _STATIC_DIR / "dist"


@app.get("/")
async def root():
    if (_DIST_DIR / "index.html").exists():
        return FileResponse(_DIST_DIR / "index.html")
    return FileResponse(_STATIC_DIR / "dashboard.html")


@app.get("/admin")
async def admin_dashboard():
    template_dir = Path(__file__).parent / "templates"
    return FileResponse(template_dir / "admin.html")


app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
