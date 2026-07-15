"""City, industry, and company distribution API."""

import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from web._settings import get_settings

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
async def get_industry_distribution(
    format: str = Query(default="flat", description="'flat' for simple list, 'tree' for hierarchical taxonomy tree"),
):
    """Return job count per industry.

    - format=flat: flat list of industries with job counts
    - format=tree: hierarchical tree (sector → division → group → industry)
    """
    try:
        neo4j = _get_neo4j(get_settings())

        if format == "tree":
            rows = neo4j.run_query(
                "MATCH (s:IndustrySector) "
                "OPTIONAL MATCH (s)<-[:BELONGS_TO_SECTOR]-(d:IndustryDivision) "
                "OPTIONAL MATCH (d)<-[:BELONGS_TO_DIVISION]-(g:IndustryGroup) "
                "OPTIONAL MATCH (g)<-[:BELONGS_TO_GROUP]-(i:Industry) "
                "OPTIONAL MATCH (i)<-[:BELONGS_TO]-(j:Job) "
                "RETURN s.code AS sector_code, s.name AS sector_name, "
                "       d.code AS division_code, d.name AS division_name, "
                "       g.code AS group_code, g.name AS group_name, "
                "       i.code AS industry_code, i.name AS industry_name, "
                "       count(DISTINCT j) AS job_count "
                "ORDER BY sector_code, division_code, group_code, industry_name"
            )

            sectors_map = {}
            divisions_map = {}
            groups_map = {}

            for row in rows:
                s_code = row["sector_code"]
                s_name = row["sector_name"]
                d_code = row["division_code"]
                d_name = row["division_name"]
                g_code = row["group_code"]
                g_name = row["group_name"]
                i_name = row["industry_name"]
                i_code = row["industry_code"]
                j_count = row["job_count"] or 0

                if s_code not in sectors_map:
                    sectors_map[s_code] = {"code": s_code, "name": s_name, "divisions": {}}

                if d_code:
                    d_key = (s_code, d_code)
                    if d_key not in divisions_map:
                        divisions_map[d_key] = {"code": d_code, "name": d_name, "groups": {}}
                        sectors_map[s_code]["divisions"][d_code] = divisions_map[d_key]

                    if g_code:
                        g_key = (s_code, d_code, g_code)
                        if g_key not in groups_map:
                            groups_map[g_key] = {"code": g_code, "name": g_name, "industries": []}
                            divisions_map[d_key]["groups"][g_code] = groups_map[g_key]

                        if i_name:
                            groups_map[g_key]["industries"].append({
                                "code": i_code,
                                "name": i_name,
                                "job_count": j_count,
                            })

            def _compute_ind_stats(node):
                if "industries" in node:
                    node["count"] = len(node["industries"])
                    node["total_demand"] = sum(i.get("job_count", 0) for i in node["industries"])
                elif "groups" in node:
                    for g in node["groups"].values():
                        _compute_ind_stats(g)
                    node["count"] = sum(g.get("count", 0) for g in node["groups"].values())
                    node["total_demand"] = sum(g.get("total_demand", 0) for g in node["groups"].values())
                elif "divisions" in node:
                    for d in node["divisions"].values():
                        _compute_ind_stats(d)
                    node["count"] = sum(d.get("count", 0) for d in node["divisions"].values())
                    node["total_demand"] = sum(d.get("total_demand", 0) for d in node["divisions"].values())

            tree = []
            for s in sectors_map.values():
                _compute_ind_stats(s)
                s["divisions"] = list(s["divisions"].values())
                for d in s["divisions"]:
                    d["groups"] = list(d["groups"].values())
                tree.append(s)

            return {"tree": tree}

        # format=flat (default) — legacy behavior
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
