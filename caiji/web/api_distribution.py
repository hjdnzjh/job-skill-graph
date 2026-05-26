"""City, industry, and company distribution API."""

import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from web.server import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["distribution"])


def _get_neo4j(settings):
    from kg.neo4j_client import Neo4jClient
    return Neo4jClient(settings)


@router.get("/cities/distribution")
async def get_city_distribution():
    """Return job count per city, ordered by count descending."""
    try:
        neo4j = _get_neo4j(get_settings())
        rows = neo4j.run_query(
            "MATCH (j:Job)-[:LOCATED_IN]->(c:City) "
            "RETURN c.name AS city, count(j) AS jobs "
            "ORDER BY jobs DESC"
        )
        return {"cities": rows}
    except Exception as exc:
        logger.error(f"City distribution API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)


@router.get("/cities/skill-profiles")
async def get_city_skill_profiles(top: int = Query(default=5, ge=1, le=20)):
    """Return top skills per city."""
    try:
        import json, os
        analytics_path = "data/kg_analytics.json"
        if os.path.exists(analytics_path):
            with open(analytics_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {"profiles": data.get("city_skill_profile", [])[:top]}

        neo4j = _get_neo4j(get_settings())
        cities = neo4j.run_query(
            "MATCH (j:Job)-[:LOCATED_IN]->(c:City) "
            "RETURN c.name AS city, count(j) AS jobs "
            "ORDER BY jobs DESC LIMIT $top",
            {"top": top},
        )
        profiles = []
        for c in cities:
            skills = neo4j.run_query(
                "MATCH (j:Job)-[:LOCATED_IN]->(:City {name: $city}), "
                "(j)-[:REQUIRES]->(s:Skill) "
                "RETURN s.name AS skill, count(*) AS count "
                "ORDER BY count DESC LIMIT 10",
                {"city": c["city"]},
            )
            profiles.append({
                "city": c["city"],
                "job_count": c["jobs"],
                "top_skills": skills,
            })
        return {"profiles": profiles}
    except Exception as exc:
        logger.error(f"City skill profiles API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)


@router.get("/industries/distribution")
async def get_industry_distribution():
    """Return job count per industry."""
    try:
        neo4j = _get_neo4j(get_settings())
        rows = neo4j.run_query(
            "MATCH (j:Job)-[:BELONGS_TO]->(i:Industry) "
            "RETURN i.name AS industry, count(j) AS jobs "
            "ORDER BY jobs DESC"
        )
        return {"industries": rows}
    except Exception as exc:
        logger.error(f"Industry distribution API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)


@router.get("/companies")
async def get_top_companies(limit: int = Query(default=20, ge=5, le=100)):
    """Return top companies ranked by job count."""
    try:
        neo4j = _get_neo4j(get_settings())
        rows = neo4j.run_query(
            "MATCH (c:Company)-[:OFFERS]->(j:Job) "
            "RETURN c.name AS company, count(j) AS jobs "
            "ORDER BY jobs DESC LIMIT $limit",
            {"limit": limit},
        )
        return {"companies": rows}
    except Exception as exc:
        logger.error(f"Companies API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)
