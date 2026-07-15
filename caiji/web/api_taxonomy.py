"""Taxonomy API — hierarchical skill, job, industry trees and cross-walk matrix."""

import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from web._settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/taxonomy", tags=["taxonomy"])


def _get_neo4j(settings):
    from kg.neo4j_client import Neo4jClient
    return Neo4jClient(settings)


# ---------------------------------------------------------------------------
# A1-A2: Skills taxonomy — 4-level tree (domain → group → type → skill)
# ---------------------------------------------------------------------------

@router.get("/skills")
async def get_skill_taxonomy():
    """Return a four-level skill taxonomy tree with aggregated demand."""
    try:
        neo4j = _get_neo4j(get_settings())
        rows = neo4j.run_query(
            "MATCH (d:SkillDomain) "
            "OPTIONAL MATCH (d)<-[:BELONGS_TO_DOMAIN]-(g:SkillGroup) "
            "OPTIONAL MATCH (g)<-[:BELONGS_TO_GROUP]-(t:SkillType) "
            "OPTIONAL MATCH (t)<-[:BELONGS_TO_TYPE]-(s:Skill) "
            "OPTIONAL MATCH (s)<-[:REQUIRES]-(j:Job) "
            "RETURN d.code AS domain_code, d.name AS domain_name, "
            "       g.code AS group_code, g.name AS group_name, "
            "       t.code AS type_code, t.name AS type_name, "
            "       s.name AS skill_name, "
            "       count(DISTINCT j) AS demand "
            "ORDER BY domain_code, group_code, type_code, skill_name"
        )

        # Assemble nested tree in Python
        domains_map = {}  # domain_code -> {code, name, groups_map}
        groups_map = {}   # (domain_code, group_code) -> {code, name, types_map}
        types_map = {}    # (domain_code, group_code, type_code) -> {code, name, skills}

        for row in rows:
            d_code = row["domain_code"]
            d_name = row["domain_name"]
            g_code = row["group_code"]
            g_name = row["group_name"]
            t_code = row["type_code"]
            t_name = row["type_name"]
            s_name = row["skill_name"]
            demand = row["demand"] or 0

            # Ensure domain
            if d_code not in domains_map:
                domains_map[d_code] = {
                    "code": d_code,
                    "name": d_name,
                    "groups": {},
                }

            if g_code:
                g_key = (d_code, g_code)
                if g_key not in groups_map:
                    groups_map[g_key] = {
                        "code": g_code,
                        "name": g_name,
                        "types": {},
                    }
                    domains_map[d_code]["groups"][g_code] = groups_map[g_key]

                if t_code:
                    t_key = (d_code, g_code, t_code)
                    if t_key not in types_map:
                        types_map[t_key] = {
                            "code": t_code,
                            "name": t_name,
                            "skills": [],
                        }
                        groups_map[g_key]["types"][t_code] = types_map[t_key]

                    if s_name:
                        types_map[t_key]["skills"].append({
                            "name": s_name,
                            "demand": demand,
                        })

        # Compute aggregated count and total_demand bottom-up
        def _compute_skill_stats(node):
            """Compute count and total_demand for a taxonomy node."""
            if "skills" in node:
                # Type level (leaf container)
                node["count"] = len(node["skills"])
                node["total_demand"] = sum(s["demand"] for s in node["skills"])
            elif "types" in node:
                # Group level
                for t in node["types"].values():
                    _compute_skill_stats(t)
                node["count"] = sum(t.get("count", 0) for t in node["types"].values())
                node["total_demand"] = sum(t.get("total_demand", 0) for t in node["types"].values())
            elif "groups" in node:
                # Domain level
                for g in node["groups"].values():
                    _compute_skill_stats(g)
                node["count"] = sum(g.get("count", 0) for g in node["groups"].values())
                node["total_demand"] = sum(g.get("total_demand", 0) for g in node["groups"].values())

        tree = []
        for d in domains_map.values():
            _compute_skill_stats(d)
            # Convert groups dict to list
            d["groups"] = list(d["groups"].values())
            for g in d["groups"]:
                g["types"] = list(g["types"].values())
            tree.append(d)

        return {"tree": tree}
    except Exception as exc:
        logger.error(f"Skill taxonomy API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)


# ---------------------------------------------------------------------------
# A3: Job taxonomy — 3-level tree (domain → category → title)
# ---------------------------------------------------------------------------

@router.get("/jobs")
async def get_job_taxonomy():
    """Return a three-level job taxonomy tree with demand and coverage."""
    try:
        neo4j = _get_neo4j(get_settings())

        # Get all job domains with categories and titles
        rows = neo4j.run_query(
            "MATCH (d:JobDomain) "
            "OPTIONAL MATCH (d)<-[:BELONGS_TO_DOMAIN]-(c:JobCategory) "
            "OPTIONAL MATCH (c)<-[:BELONGS_TO_CATEGORY]-(t:JobTitle) "
            "OPTIONAL MATCH (t)<-[:HAS_TITLE]-(j:Job) "
            "RETURN d.code AS domain_code, d.name AS domain_name, "
            "       c.code AS category_code, c.name AS category_name, "
            "       t.code AS title_code, t.name AS title_name, "
            "       count(DISTINCT j) AS job_count "
            "ORDER BY domain_code, category_code, title_name"
        )

        # Assemble nested tree
        domains_map = {}
        categories_map = {}

        for row in rows:
            d_code = row["domain_code"]
            d_name = row["domain_name"]
            c_code = row["category_code"]
            c_name = row["category_name"]
            t_name = row["title_name"]
            t_code = row["title_code"]
            j_count = row["job_count"] or 0

            if d_code not in domains_map:
                domains_map[d_code] = {
                    "code": d_code,
                    "name": d_name,
                    "categories": {},
                }

            if c_code:
                c_key = (d_code, c_code)
                if c_key not in categories_map:
                    categories_map[c_key] = {
                        "code": c_code,
                        "name": c_name,
                        "titles": [],
                    }
                    domains_map[d_code]["categories"][c_code] = categories_map[c_key]

                if t_name:
                    categories_map[c_key]["titles"].append({
                        "code": t_code,
                        "name": t_name,
                        "job_count": j_count,
                    })

        # Compute stats
        def _compute_job_stats(node):
            if "titles" in node:
                node["count"] = len(node["titles"])
                node["total_demand"] = sum(t.get("job_count", 0) for t in node["titles"])
            elif "categories" in node:
                for c in node["categories"].values():
                    _compute_job_stats(c)
                node["count"] = sum(c.get("count", 0) for c in node["categories"].values())
                node["total_demand"] = sum(c.get("total_demand", 0) for c in node["categories"].values())

        tree = []
        for d in domains_map.values():
            _compute_job_stats(d)
            d["categories"] = list(d["categories"].values())
            tree.append(d)

        # Classification coverage: proportion of JobTitle nodes with a domain_code
        coverage_row = neo4j.run_query(
            "MATCH (t:JobTitle) "
            "RETURN count(t) AS total, "
            "       count(CASE WHEN t.domain_code IS NOT NULL THEN 1 END) AS classified"
        )
        total = coverage_row[0]["total"] if coverage_row else 0
        classified = coverage_row[0]["classified"] if coverage_row else 0
        classification_coverage = round(classified / total, 4) if total > 0 else 0.0

        return {
            "tree": tree,
            "classification_coverage": classification_coverage,
            "total_titles": total,
            "classified_titles": classified,
        }
    except Exception as exc:
        logger.error(f"Job taxonomy API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)


# ---------------------------------------------------------------------------
# A4: Industry taxonomy — 3-level tree (sector → division → group → industry)
# ---------------------------------------------------------------------------

@router.get("/industries")
async def get_industry_taxonomy():
    """Return a three-level industry taxonomy tree with job demand."""
    try:
        neo4j = _get_neo4j(get_settings())
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

        # Assemble nested tree
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
                sectors_map[s_code] = {
                    "code": s_code,
                    "name": s_name,
                    "divisions": {},
                }

            if d_code:
                d_key = (s_code, d_code)
                if d_key not in divisions_map:
                    divisions_map[d_key] = {
                        "code": d_code,
                        "name": d_name,
                        "groups": {},
                    }
                    sectors_map[s_code]["divisions"][d_code] = divisions_map[d_key]

                if g_code:
                    g_key = (s_code, d_code, g_code)
                    if g_key not in groups_map:
                        groups_map[g_key] = {
                            "code": g_code,
                            "name": g_name,
                            "industries": [],
                        }
                        divisions_map[d_key]["groups"][g_code] = groups_map[g_key]

                    if i_name:
                        groups_map[g_key]["industries"].append({
                            "code": i_code,
                            "name": i_name,
                            "job_count": j_count,
                        })

        # Compute stats
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
    except Exception as exc:
        logger.error(f"Industry taxonomy API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)


# ---------------------------------------------------------------------------
# A5: Cross-walk — job-domain × skill-domain matrix
# ---------------------------------------------------------------------------

@router.get("/cross-walk")
async def get_cross_walk():
    """Return a job-domain × skill-domain overlap matrix."""
    try:
        neo4j = _get_neo4j(get_settings())
        rows = neo4j.run_query(
            "MATCH (d:JobDomain) "
            "MATCH (sd:SkillDomain) "
            "OPTIONAL MATCH (:JobTitle {domain_code: d.code})<-[:HAS_TITLE]-(j:Job)-[:REQUIRES]->(:Skill {domain_code: sd.code}) "
            "WITH d, sd, count(j) AS overlap "
            "RETURN d.code AS job_domain_code, d.name AS job_domain_name, "
            "       sd.code AS skill_domain_code, sd.name AS skill_domain_name, "
            "       overlap "
            "ORDER BY d.code, sd.code"
        )

        matrix = []
        for r in rows:
            matrix.append({
                "job_domain_code": r["job_domain_code"],
                "job_domain_name": r["job_domain_name"],
                "skill_domain_code": r["skill_domain_code"],
                "skill_domain_name": r["skill_domain_name"],
                "overlap": r["overlap"] or 0,
            })

        return {"matrix": matrix}
    except Exception as exc:
        logger.error(f"Cross-walk API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)
