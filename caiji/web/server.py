"""FastAPI application: route registration, CORS, static file serving."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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

# Lazy settings singleton — works with both uvicorn and TestClient
_settings = None


def get_settings():
    global _settings
    if _settings is None:
        from config.settings import Settings
        _settings = Settings()
    return _settings


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

# Serve SPA at / (dashboard.html fallback if SPA not built)
from fastapi.responses import FileResponse

_STATIC_DIR = Path(__file__).parent / "static"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)
_DIST_DIR = _STATIC_DIR / "dist"


@app.get("/")
async def root():
    if (_DIST_DIR / "index.html").exists():
        return FileResponse(_DIST_DIR / "index.html")
    return FileResponse(_STATIC_DIR / "dashboard.html")


# Mount static for any other files (font, images, SPA assets, etc.)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
