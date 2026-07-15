"""Skill ranking, network, communities, and categories API."""

import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from web._settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/skills", tags=["skills"])


def _get_neo4j(settings):
    from kg.neo4j_client import Neo4jClient
    return Neo4jClient(settings)


@router.get("/ranking")
async def get_skill_ranking(
    limit: int = Query(default=30, ge=5, le=100),
    domain: str = Query(default=None, description="Filter by skill domain_code"),
    group: str = Query(default=None, description="Filter by skill group_code"),
):
    """Return top skills ranked by REQUIRES demand. Optional domain/group filters."""
    try:
        neo4j = _get_neo4j(get_settings())
        rows = neo4j.run_query(
            "MATCH (:Job)-[:REQUIRES]->(s:Skill) "
            "WHERE ($domain IS NULL OR s.domain_code = $domain) "
            "  AND ($group IS NULL OR s.group_code = $group) "
            "RETURN s.name AS name, s.category AS category, count(*) AS demand, "
            "       s.domain_code AS domain_code, s.domain_name AS domain_name, "
            "       s.group_code AS group_code, s.group_name AS group_name, "
            "       s.type_code AS type_code, s.type_name AS type_name "
            "ORDER BY demand DESC LIMIT $limit",
            {"limit": limit, "domain": domain, "group": group},
        )
        return {"skills": rows}
    except Exception as exc:
        logger.error(f"Skill ranking API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)


@router.get("/network")
async def get_skill_network(limit: int = Query(default=50, ge=10, le=200)):
    """Return skill co-occurrence network for force-directed graph."""
    try:
        neo4j = _get_neo4j(get_settings())
        edges = neo4j.run_query(
            "MATCH (a:Skill)-[r:CO_OCCURS_WITH]->(b:Skill) "
            "WHERE a.name < b.name "
            "RETURN a.name AS source, b.name AS target, r.weight AS weight "
            "ORDER BY r.weight DESC LIMIT $limit",
            {"limit": limit * 2},
        )
        seen = {}
        for e in edges:
            for name in (e["source"], e["target"]):
                if name not in seen:
                    seen[name] = True
        node_names = list(seen.keys())

        demand_rows = neo4j.run_query(
            "MATCH (:Job)-[:REQUIRES]->(s:Skill) "
            "WHERE s.name IN $names "
            "RETURN s.name AS name, s.category AS category, s.domain_code AS domain_code, count(*) AS demand",
            {"names": node_names},
        )
        demand_map = {r["name"]: r for r in demand_rows}

        nodes = []
        for name in node_names:
            info = demand_map.get(name, {})
            nodes.append({
                "name": name,
                "category": info.get("category", ""),
                "domain_code": info.get("domain_code", ""),
                "demand": info.get("demand", 1),
            })

        return {"nodes": nodes, "edges": edges}
    except Exception as exc:
        logger.error(f"Skill network API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)


@router.get("/communities")
async def get_skill_communities():
    """Return skill community detection results."""
    try:
        import json, os
        analytics_path = "data/kg_analytics.json"
        if os.path.exists(analytics_path):
            with open(analytics_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("skill_communities", {})
            clusters = []
            for key, val in raw.items():
                clusters.append({
                    "id": key,
                    "size": val.get("size", 0),
                    "top_skills": val.get("top_skills", []),
                })
            return {"clusters": clusters}

        neo4j = _get_neo4j(get_settings())
        edges = neo4j.run_query(
            "MATCH (a:Skill)-[r:CO_OCCURS_WITH]->(b:Skill) "
            "RETURN a.name AS skill_a, b.name AS skill_b, r.weight AS weight"
        )
        if not edges:
            return {"clusters": []}

        import networkx as nx
        from networkx.algorithms.community import louvain_communities
        G = nx.Graph()
        for e in edges:
            G.add_edge(e["skill_a"], e["skill_b"], weight=e.get("weight", 1))
        communities = louvain_communities(G)
        clusters = []
        for i, comm in enumerate(communities):
            clusters.append({
                "id": f"cluster_{i}",
                "size": len(comm),
                "top_skills": list(comm)[:10],
            })
        return {"clusters": clusters}
    except Exception as exc:
        logger.error(f"Skill communities API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)


@router.get("/categories")
async def get_skill_categories(
    format: str = Query(default="tree", description="'tree' for taxonomy tree, 'flat' for legacy category grouping"),
):
    """Return skills grouped by category for pie/sunburst charts.

    - format=tree: hierarchical taxonomy tree from Neo4j SkillDomain/Group/Type nodes
    - format=flat: legacy flat grouping by s.category string
    """
    try:
        neo4j = _get_neo4j(get_settings())

        if format == "flat":
            # Legacy behaviour — group by s.category string
            rows = neo4j.run_query(
                "MATCH (:Job)-[:REQUIRES]->(s:Skill) "
                "RETURN s.category AS category, s.name AS name, count(*) AS demand "
                "ORDER BY s.category, demand DESC"
            )
            cat_map = {}
            for r in rows:
                cat = r["category"] or "未分类"
                if cat not in cat_map:
                    cat_map[cat] = {"name": cat, "total_demand": 0, "skills": []}
                cat_map[cat]["total_demand"] += r["demand"]
                cat_map[cat]["skills"].append({
                    "name": r["name"],
                    "demand": r["demand"],
                })
            categories = sorted(cat_map.values(), key=lambda x: -x["total_demand"])
            return {"categories": categories}

        # format=tree — read from Neo4j taxonomy
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

        domains_map = {}
        groups_map = {}
        types_map = {}

        for row in rows:
            d_code = row["domain_code"]
            d_name = row["domain_name"]
            g_code = row["group_code"]
            g_name = row["group_name"]
            t_code = row["type_code"]
            t_name = row["type_name"]
            s_name = row["skill_name"]
            demand = row["demand"] or 0

            if d_code not in domains_map:
                domains_map[d_code] = {"code": d_code, "name": d_name, "groups": {}}

            if g_code:
                g_key = (d_code, g_code)
                if g_key not in groups_map:
                    groups_map[g_key] = {"code": g_code, "name": g_name, "types": {}}
                    domains_map[d_code]["groups"][g_code] = groups_map[g_key]

                if t_code:
                    t_key = (d_code, g_code, t_code)
                    if t_key not in types_map:
                        types_map[t_key] = {"code": t_code, "name": t_name, "skills": []}
                        groups_map[g_key]["types"][t_code] = types_map[t_key]

                    if s_name:
                        types_map[t_key]["skills"].append({"name": s_name, "demand": demand})

        def _compute_stats(node):
            if "skills" in node:
                node["count"] = len(node["skills"])
                node["total_demand"] = sum(s["demand"] for s in node["skills"])
            elif "types" in node:
                for t in node["types"].values():
                    _compute_stats(t)
                node["count"] = sum(t.get("count", 0) for t in node["types"].values())
                node["total_demand"] = sum(t.get("total_demand", 0) for t in node["types"].values())
            elif "groups" in node:
                for g in node["groups"].values():
                    _compute_stats(g)
                node["count"] = sum(g.get("count", 0) for g in node["groups"].values())
                node["total_demand"] = sum(g.get("total_demand", 0) for g in node["groups"].values())

        tree = []
        for d in domains_map.values():
            _compute_stats(d)
            d["groups"] = list(d["groups"].values())
            for g in d["groups"]:
                g["types"] = list(g["types"].values())
            tree.append(d)

        return {"tree": tree}
    except Exception as exc:
        logger.error(f"Skill categories API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)
