"""Salary analysis API."""

import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from web.server import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/salary", tags=["salary"])


def _get_neo4j(settings):
    from kg.neo4j_client import Neo4jClient
    return Neo4jClient(settings)


@router.get("/by-title")
async def get_salary_by_title(limit: int = Query(default=15, ge=5, le=50)):
    """Return average salary min/max per job title."""
    try:
        neo4j = _get_neo4j(get_settings())
        rows = neo4j.run_query(
            "MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle) "
            "WHERE j.salary_min IS NOT NULL AND j.salary_max IS NOT NULL "
            "RETURN t.name AS title, "
            "round(avg(j.salary_min), 1) AS avg_min, "
            "round(avg(j.salary_max), 1) AS avg_max, "
            "count(j) AS cnt "
            "ORDER BY cnt DESC LIMIT $limit",
            {"limit": limit},
        )
        return {"salaries": rows}
    except Exception as exc:
        logger.error(f"Salary by title API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)


@router.get("/by-city")
async def get_salary_by_city():
    """Return average salary per city."""
    try:
        neo4j = _get_neo4j(get_settings())
        rows = neo4j.run_query(
            "MATCH (j:Job)-[:LOCATED_IN]->(c:City) "
            "WHERE j.salary_min IS NOT NULL AND j.salary_max IS NOT NULL "
            "RETURN c.name AS city, "
            "round(avg(j.salary_min), 1) AS avg_min, "
            "round(avg(j.salary_max), 1) AS avg_max, "
            "count(j) AS cnt "
            "ORDER BY cnt DESC"
        )
        return {"salaries": rows}
    except Exception as exc:
        logger.error(f"Salary by city API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)
