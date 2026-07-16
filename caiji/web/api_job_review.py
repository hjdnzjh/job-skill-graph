"""Job review API: list pending jobs, approve, reject, update details.

Provides the backend for the JobReview admin page, handling the
review workflow for both regular Job nodes and EmergingJob nodes.

Authentication:
    - Review actions (approve/reject/update) require X-Admin-Key header
      matching ADMIN_API_KEY environment variable.
    - List and detail endpoints are publicly readable (no auth).
"""

import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from web._settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["job-review"])


def _verify_admin(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    """依赖注入：校验管理端 API 密钥，保护写操作。密钥统一从 Settings 读取。"""
    from web._settings import get_settings
    admin_key = get_settings().admin_api_key
    if not admin_key:
        logger.warning("ADMIN_API_KEY 未设置——管理端点处于无认证状态")
        return True
    if x_admin_key != admin_key:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="需要管理员密钥（X-Admin-Key）",
        )
    return True


def _get_neo4j():
    from kg.neo4j_client import Neo4jClient
    return Neo4jClient(get_settings())


def _format_ts(value) -> str:
    """Convert Neo4j timestamp or ISO string to ISO date string."""
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000).isoformat()
    return str(value)[:19]


class JobUpdateBody(BaseModel):
    description: Optional[str] = Field(None, description="Job description")
    required_skills: Optional[list[str]] = Field(None, description="Required skill names")
    industries: Optional[list[str]] = Field(None, description="Industry categories")


@router.get("/pending")
async def list_pending(
    search: Optional[str] = Query(None, description="Search by job title"),
    status: Optional[str] = Query(None, description="Filter by status (pending/active/archived)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List jobs for review with database-level pagination.

    Returns EmergingJob nodes (needing review) with pagination metadata.
    """
    try:
        neo4j = _get_neo4j()

        # Build WHERE clause parts
        conditions = []
        params = {}
        if search:
            conditions.append("e.name CONTAINS $search")
            params["search"] = search
        if status:
            conditions.append("e.status = $status")
            params["status"] = status
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        # Count total
        total_result = neo4j.run_query(
            "MATCH (e:EmergingJob)" + where_clause + " RETURN count(e) AS cnt",
            params,
        )
        total = total_result[0]["cnt"] if total_result else 0

        # Fetch paginated — database-level SKIP/LIMIT
        params["limit"] = limit
        params["offset"] = offset
        emerging = neo4j.run_query(
            "MATCH (e:EmergingJob)"
            + where_clause
            + " RETURN e.name AS title, e.status AS status,"
            "        e.confidence AS confidence,"
            "        e.responsibilities AS description,"
            "        e.job_count AS job_count,"
            "        e.imported_at AS date"
            " ORDER BY e.confidence DESC SKIP $offset LIMIT $limit",
            params,
        )

        neo4j.close()

        jobs = []
        for j in emerging:
            jobs.append({
                "title": j.get("title", ""),
                "category": "新兴岗位",
                "source": "AI挖掘",
                "status": j.get("status", "pending"),
                "date": _format_ts(j.get("date"))[:10],
                "confidence": j.get("confidence"),
                "description": (j.get("description") or "")[:200],
                "type": "emerging",
            })

        return {
            "jobs": jobs,
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    except Exception as exc:
        logger.error(f"Job review list error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/{title}")
async def get_job_detail(title: str):
    """Get full details for a specific job by title.

    Fetches from EmergingJob first, then falls back to JobTitle.
    Returns unified format with required_skills as object array.
    """
    try:
        neo4j = _get_neo4j()

        # Try EmergingJob first
        emerging = neo4j.run_query(
            "MATCH (e:EmergingJob {name: $title}) "
            "RETURN e.name AS title, 'emerging' AS type, "
            "       e.responsibilities AS description, "
            "       e.confidence AS confidence, e.job_count AS job_count, "
            "       e.status AS status",
            {"title": title},
        )

        if emerging:
            job = emerging[0]
            skills = neo4j.run_query(
                "MATCH (e:EmergingJob {name: $title})-[:REQUIRES]->(s:Skill) "
                "RETURN s.name AS skill, s.category AS category",
                {"title": title},
            )
            preferred = neo4j.run_query(
                "MATCH (e:EmergingJob {name: $title})-[:PREFERS]->(s:Skill) "
                "RETURN s.name AS skill",
                {"title": title},
            )
            industries = neo4j.run_query(
                "MATCH (e:EmergingJob {name: $title})-[:BELONGS_TO]->(i:Industry) "
                "RETURN i.name AS industry",
                {"title": title},
            )
            neo4j.close()
            return {
                "title": job.get("title", title),
                "type": "emerging",
                "status": job.get("status", "pending"),
                "description": job.get("description", ""),
                "confidence": job.get("confidence"),
                "job_count": job.get("job_count", 0),
                "required_skills": [{"name": s["skill"], "category": s.get("category", "")} for s in skills],
                "preferred_skills": [{"name": s["skill"], "category": ""} for s in preferred],
                "industries": [i["industry"] for i in industries],
            }

        # Fallback to regular JobTitle
        titles = neo4j.run_query(
            "MATCH (t:JobTitle {name: $title}) "
            "RETURN t.name AS title, exists((:Job)-[:HAS_TITLE]->(t)) AS has_jobs",
            {"title": title},
        )
        if not titles:
            neo4j.close()
            return JSONResponse({"error": f"岗位 '{title}' 不存在"}, status_code=404)

        stats = neo4j.run_query(
            "MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle {name: $title}) "
            "RETURN count(j) AS job_count, "
            "       avg(j.salary_min) AS avg_min, avg(j.salary_max) AS avg_max, "
            "       max(j.crawl_timestamp) AS latest_date",
            {"title": title},
        )
        skills = neo4j.run_query(
            "MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle {name: $title}), "
            "(j)-[:REQUIRES]->(s:Skill) "
            "RETURN s.name AS skill, s.category AS category, "
            "count(*) AS demand ORDER BY demand DESC LIMIT 20",
            {"title": title},
        )
        neo4j.close()

        s = stats[0] if stats else {}
        return {
            "title": title,
            "type": "regular",
            "status": "active",
            "description": "",
            "job_count": s.get("job_count", 0),
            "avg_salary_min": round(s.get("avg_min") or 0, 1),
            "avg_salary_max": round(s.get("avg_max") or 0, 1),
            "latest_date": _format_ts(s.get("latest_date", "")),
            "required_skills": [
                {"name": sk["skill"], "category": sk.get("category", ""), "demand": sk.get("demand", 0)}
                for sk in skills
            ],
        }

    except Exception as exc:
        logger.error(f"Job detail error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/{title}/approve")
async def approve_job(title: str, _auth=Depends(_verify_admin)):
    """Approve a job (set status to 'active'). Requires admin auth."""
    try:
        neo4j = _get_neo4j()
        result = neo4j.run_query(
            "MATCH (e:EmergingJob {name: $title}) "
            "SET e.status = 'active', e.reviewed_at = timestamp() "
            "RETURN e.name AS title, e.status AS status",
            {"title": title},
        )
        if result:
            neo4j.close()
            return {
                "status": "approved",
                "title": title,
                "type": "emerging",
                "reviewed_at": datetime.now().isoformat(),
            }

        neo4j.close()
        return JSONResponse(
            {"error": f"岗位 '{title}' 无法审批（已经是 regular 类型，无须审核）"},
            status_code=404,
        )
    except Exception as exc:
        logger.error(f"Job approve error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/{title}/reject")
async def reject_job(title: str, _auth=Depends(_verify_admin)):
    """Reject a job (set status to 'archived'). Requires admin auth."""
    try:
        neo4j = _get_neo4j()
        result = neo4j.run_query(
            "MATCH (e:EmergingJob {name: $title}) "
            "SET e.status = 'archived', e.reviewed_at = timestamp() "
            "RETURN e.name AS title, e.status AS status",
            {"title": title},
        )
        if result:
            neo4j.close()
            return {
                "status": "rejected",
                "title": title,
                "type": "emerging",
                "reviewed_at": datetime.now().isoformat(),
            }

        neo4j.close()
        return JSONResponse(
            {"error": f"岗位 '{title}' 不存在或无法驳回"},
            status_code=404,
        )
    except Exception as exc:
        logger.error(f"Job reject error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.put("/{title}")
async def update_job(title: str, body: JobUpdateBody, _auth=Depends(_verify_admin)):
    """Update job details (description, skills, industries). Requires admin auth."""
    try:
        neo4j = _get_neo4j()

        # Update description
        if body.description is not None:
            neo4j.run_query(
                "MATCH (e:EmergingJob {name: $title}) "
                "SET e.responsibilities = $desc",
                {"title": title, "desc": body.description},
            )

        # Update skills
        if body.required_skills is not None:
            neo4j.run_query(
                "MATCH (e:EmergingJob {name: $title})-[r:REQUIRES]->(s:Skill) DELETE r",
                {"title": title},
            )
            for skill_name in body.required_skills:
                neo4j.run_query(
                    "MATCH (e:EmergingJob {name: $title}) "
                    "MERGE (s:Skill {name: $skill}) "
                    "MERGE (e)-[:REQUIRES]->(s)",
                    {"title": title, "skill": skill_name},
                )

        # Update industries
        if body.industries is not None:
            neo4j.run_query(
                "MATCH (e:EmergingJob {name: $title})-[r:BELONGS_TO]->(:Industry) DELETE r",
                {"title": title},
            )
            for ind_name in body.industries:
                neo4j.run_query(
                    "MATCH (e:EmergingJob {name: $title}) "
                    "MERGE (i:Industry {name: $ind}) "
                    "MERGE (e)-[:BELONGS_TO]->(i)",
                    {"title": title, "ind": ind_name},
                )

        neo4j.close()
        return {"status": "updated", "title": title}

    except Exception as exc:
        logger.error(f"Job update error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)
