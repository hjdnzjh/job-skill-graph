"""Job capability update API."""

import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from web._settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/updater", tags=["updater"])


@router.get("/analyze")
async def analyze_job(title: str):
    """Analyze skill changes for a job title."""
    try:
        from kg.job_updater import JobUpdater
        updater = JobUpdater(get_settings())
        result = updater.analyze(title)
        return result
    except Exception as exc:
        logger.error(f"Job updater API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/list")
async def list_updatable():
    """List jobs that have canonical baselines available."""
    try:
        from kg.job_updater import JobUpdater
        updater = JobUpdater(get_settings())
        jobs = updater.list_updatable_jobs()
        return {"jobs": jobs}
    except Exception as exc:
        logger.error(f"Job updater list error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)
