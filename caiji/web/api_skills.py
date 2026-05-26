"""Skill ranking, network, communities, and categories API."""

import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from web.server import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/skills", tags=["skills"])


def _get_neo4j(settings):
    from kg.neo4j_client import Neo4jClient
    return Neo4jClient(settings)


@router.get("/ranking")
async def get_skill_ranking(limit: int = Query(default=30, ge=5, le=100)):
    """Return top skills ranked by REQUIRES demand."""
    try:
        neo4j = _get_neo4j(get_settings())
        rows = neo4j.run_query(
            "MATCH (:Job)-[:REQUIRES]->(s:Skill) "
            "RETURN s.name AS name, s.category AS category, count(*) AS demand "
            "ORDER BY demand DESC LIMIT $limit",
            {"limit": limit},
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
            "RETURN s.name AS name, s.category AS category, count(*) AS demand",
            {"names": node_names},
        )
        demand_map = {r["name"]: r for r in demand_rows}

        nodes = []
        for name in node_names:
            info = demand_map.get(name, {})
            nodes.append({
                "name": name,
                "category": info.get("category", ""),
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
async def get_skill_categories():
    """Return skills grouped by category for pie/sunburst charts."""
    try:
        neo4j = _get_neo4j(get_settings())
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
    except Exception as exc:
        logger.error(f"Skill categories API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=503)
