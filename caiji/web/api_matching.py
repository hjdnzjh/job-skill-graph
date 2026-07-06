"""Person-job matching and recommendation API."""

import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from web._settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["matching"])


class MatchRequest(BaseModel):
    skills: list[str] = Field(..., min_length=1, description="User skills")
    target: str = Field(..., min_length=1, description="Target job title")


class RecommendRequest(BaseModel):
    skills: list[str] = Field(..., min_length=1)
    top_n: int = Field(default=10, ge=1, le=50)


@router.get("/job-titles")
async def get_job_titles():
    """Return all matchable job titles."""
    from kg.job_matcher import JobMatcher
    try:
        matcher = JobMatcher(get_settings())
        titles = matcher.list_available_titles()
        matcher.close()
        return {"titles": titles}
    except Exception as exc:
        logger.error(f"Job titles API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)


@router.post("/match")
async def match_skills(body: MatchRequest):
    """Match user skills against a target job."""
    from kg.job_matcher import JobMatcher
    try:
        matcher = JobMatcher(get_settings())
        resolved = matcher.find_title(body.target)
        if not resolved:
            matcher.close()
            return JSONResponse(
                {"error": f"未找到岗位 '{body.target}'，请使用 /api/job-titles 查看可匹配岗位"},
                status_code=404,
            )
        result = matcher.match(body.skills, resolved)
        matcher.close()
        return result
    except Exception as exc:
        logger.error(f"Match API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/recommend")
async def recommend_jobs(body: RecommendRequest):
    """Recommend best-matching job titles for a given skill set."""
    from kg.job_matcher import JobMatcher
    try:
        matcher = JobMatcher(get_settings())
        recommendations = matcher.recommend_jobs(body.skills, top_n=body.top_n)
        matcher.close()
        return {"recommendations": recommendations}
    except Exception as exc:
        logger.error(f"Recommend API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)
