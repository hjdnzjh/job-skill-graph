"""Overview statistics and emerging jobs API."""

import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from web._settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["overview"])


def _get_neo4j(settings):
    from kg.neo4j_client import Neo4jClient
    return Neo4jClient(settings)


def _get_taxonomy_counts(neo4j):
    """Return counts of all taxonomy classification nodes."""
    try:
        rows = neo4j.run_query(
            "MATCH (n) "
            "WHERE n:SkillDomain OR n:SkillGroup OR n:SkillType "
            "   OR n:JobDomain OR n:JobCategory "
            "   OR n:IndustrySector OR n:IndustryDivision OR n:IndustryGroup "
            "RETURN labels(n)[0] AS label, count(n) AS cnt"
        )
        return {r["label"]: r["cnt"] for r in rows}
    except Exception:
        return {}


def _get_domain_distribution(neo4j):
    """Return job and skill distributions across domains."""
    try:
        jobs = neo4j.run_query(
            "MATCH (d:JobDomain) "
            "OPTIONAL MATCH (:JobTitle {domain_code: d.code})<-[:HAS_TITLE]-(j:Job) "
            "RETURN d.code AS code, d.name AS name, count(j) AS job_count "
            "ORDER BY d.code"
        )
        skills = neo4j.run_query(
            "MATCH (d:SkillDomain) "
            "OPTIONAL MATCH (s:Skill {domain_code: d.code}) "
            "OPTIONAL MATCH (j:Job)-[:REQUIRES]->(s) "
            "RETURN d.code AS code, d.name AS name, "
            "       count(DISTINCT s) AS skill_count, "
            "       count(DISTINCT j) AS demand "
            "ORDER BY d.code"
        )
        return {
            "jobs": jobs,
            "skills": skills,
        }
    except Exception:
        return {"jobs": [], "skills": []}


@router.get("/overview")
async def get_overview():
    """Return graph-wide KPI statistics."""
    settings = get_settings()
    try:
        neo4j = _get_neo4j(settings)
        rows = neo4j.run_query(
            "MATCH (n) "
            "RETURN labels(n)[0] AS label, count(n) AS cnt "
            "ORDER BY cnt DESC"
        )
        nodes_by_label = {r["label"]: r["cnt"] for r in rows}
        total_nodes = sum(nodes_by_label.values())

        rel_rows = neo4j.run_query(
            "MATCH ()-[r]->() "
            "RETURN type(r) AS rel_type, count(r) AS cnt "
            "ORDER BY cnt DESC"
        )
        rels_by_type = {r["rel_type"]: r["cnt"] for r in rel_rows}
        total_edges = sum(rels_by_type.values())

        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "total_jobs": nodes_by_label.get("Job", 0),
            "total_skills": nodes_by_label.get("Skill", 0),
            "total_companies": nodes_by_label.get("Company", 0),
            "total_cities": nodes_by_label.get("City", 0),
            "total_industries": nodes_by_label.get("Industry", 0),
            "nodes_by_label": nodes_by_label,
            "relationships_by_type": rels_by_type,
            "taxonomy": _get_taxonomy_counts(neo4j),
            "domain_distribution": _get_domain_distribution(neo4j),
        }
    except Exception as exc:
        logger.error(f"Overview API error: {exc}")
        return JSONResponse(
            {"error": f"Neo4j 查询失败: {exc}"}, status_code=503
        )


@router.get("/emerging-jobs")
async def get_emerging_jobs():
    """List discovered emerging job roles."""
    settings = get_settings()
    try:
        from kg.job_discovery import EmergingJobDetector
        detector = EmergingJobDetector(settings)
        jobs = detector.list_emerging()
        detector.close()
        return {"emerging_jobs": jobs}
    except Exception as exc:
        logger.error(f"Emerging jobs API error: {exc}")
        return JSONResponse(
            {"error": f"查询失败: {exc}"}, status_code=503
        )
