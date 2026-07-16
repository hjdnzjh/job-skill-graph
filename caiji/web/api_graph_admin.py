"""Graph administration API for admin dashboard.

Provides CRUD operations for Neo4j nodes and edges, plus export.
"""

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from web._settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph-admin"])


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


class NodeCreate(BaseModel):
    label: str = Field(..., min_length=1, description="Node label (e.g. Skill, JobTitle)")
    name: str = Field(..., min_length=1, description="Node name")
    properties: dict = Field(default_factory=dict, description="Additional properties")


class NodeUpdate(BaseModel):
    properties: dict = Field(..., min_length=1, description="Properties to update")


class EdgeCreate(BaseModel):
    source_label: str = Field(..., description="Source node label")
    source_key: str = Field(default="name", description="Source node property key")
    source_value: str = Field(..., description="Source node property value")
    target_label: str = Field(..., description="Target node label")
    target_key: str = Field(default="name", description="Target node property key")
    target_value: str = Field(..., description="Target node property value")
    rel_type: str = Field(..., min_length=1, description="Relationship type")
    properties: dict = Field(default_factory=dict)


def _get_neo4j():
    from kg.neo4j_client import Neo4jClient
    return Neo4jClient(get_settings())


@router.get("/nodes")
async def list_nodes(
    label: Optional[str] = Query(None, description="Filter by node label"),
    search: Optional[str] = Query(None, description="Search by name"),
    limit: int = Query(default=200, ge=1, le=1000),
):
    """List all nodes in the graph, optionally filtered by label."""
    try:
        neo4j = _get_neo4j()
        where = ""
        params = {"limit": limit}
        if label:
            where = "WHERE labels(n)[0] = $label"
            params["label"] = label
        if search and label:
            where = "WHERE labels(n)[0] = $label AND n.name CONTAINS $search"
            params["search"] = search
        elif search:
            where = "WHERE n.name CONTAINS $search"
            params["search"] = search

        rows = neo4j.run_query(
            f"MATCH (n) {where} "
            f"RETURN labels(n)[0] AS label, n.name AS name, "
            f"n.category AS category, id(n) AS node_id "
            f"ORDER BY label, name LIMIT $limit",
            params,
        )
        neo4j.close()
        # Clean null values for frontend safety
        for r in rows:
            r["category"] = r.get("category") or ""
        return {"nodes": rows, "total": len(rows)}
    except Exception as exc:
        logger.error(f"Graph list nodes error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/nodes")
async def create_node(body: NodeCreate, _auth=Depends(_verify_admin)):
    """Create a new node in the graph."""
    try:
        neo4j = _get_neo4j()
        props = body.properties
        props["name"] = body.name

        set_clauses = ", ".join(
            f"n.{k} = ${k}" for k in props.keys()
        )
        params = {k: v for k, v in props.items()}

        result = neo4j.run_query(
            f"CREATE (n:{body.label} {{{set_clauses}}}) "
            f"RETURN labels(n)[0] AS label, n.name AS name, id(n) AS node_id",
            params,
        )
        neo4j.close()

        if result:
            return {"status": "created", "node": result[0]}
        return JSONResponse({"error": "创建节点失败"}, status_code=500)
    except Exception as exc:
        logger.error(f"Graph create node error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.put("/nodes/{node_id}")
async def update_node(node_id: int, body: NodeUpdate, _auth=Depends(_verify_admin)):
    """Update properties of an existing node."""
    try:
        neo4j = _get_neo4j()
        set_clauses = ", ".join(
            f"n.{k} = ${k}" for k in body.properties.keys()
        )
        params = {k: v for k, v in body.properties.items()}
        params["node_id"] = node_id

        result = neo4j.run_query(
            f"MATCH (n) WHERE id(n) = $node_id "
            f"SET {set_clauses} "
            f"RETURN labels(n)[0] AS label, n.name AS name, id(n) AS node_id",
            params,
        )
        neo4j.close()

        if result:
            return {"status": "updated", "node": result[0]}
        return JSONResponse({"error": "未找到节点"}, status_code=404)
    except Exception as exc:
        logger.error(f"Graph update node error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: int, _auth=Depends(_verify_admin)):
    """Delete a node and its relationships. Returns count of affected edges."""
    try:
        neo4j = _get_neo4j()
        # Count edges first
        edges_count = neo4j.run_query(
            "MATCH (n) WHERE id(n) = $node_id OPTIONAL MATCH (n)-[r]-() "
            "RETURN count(r) AS edge_count",
            {"node_id": node_id},
        )
        affected_edges = edges_count[0]["edge_count"] if edges_count else 0

        neo4j.run_query(
            "MATCH (n) WHERE id(n) = $node_id DETACH DELETE n",
            {"node_id": node_id},
        )
        neo4j.close()
        return {
            "status": "deleted",
            "node_id": node_id,
            "edges_deleted": affected_edges,
        }
    except Exception as exc:
        logger.error(f"Graph delete node error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/edges")
async def list_edges(
    rel_type: Optional[str] = Query(None, description="Filter by relationship type"),
    limit: int = Query(default=200, ge=1, le=1000),
):
    """List relationships in the graph."""
    try:
        neo4j = _get_neo4j()
        where = ""
        params = {"limit": limit}
        if rel_type:
            where = "WHERE type(r) = $rel_type"
            params["rel_type"] = rel_type

        rows = neo4j.run_query(
            f"MATCH (a)-[r]->(b) {where} "
            f"RETURN labels(a)[0] AS source_label, a.name AS source_name, "
            f"       type(r) AS rel_type, "
            f"       labels(b)[0] AS target_label, b.name AS target_name, "
            f"       id(r) AS edge_id "
            f"ORDER BY rel_type LIMIT $limit",
            params,
        )
        neo4j.close()
        return {"edges": rows, "total": len(rows)}
    except Exception as exc:
        logger.error(f"Graph list edges error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/edges")
async def create_edge(body: EdgeCreate, _auth=Depends(_verify_admin)):
    """Create a relationship between two nodes."""
    try:
        neo4j = _get_neo4j()
        src_label = body.source_label.replace("`", "")
        tgt_label = body.target_label.replace("`", "")
        rel = body.rel_type.replace("`", "")

        set_clause = ""
        params = {
            "sv": body.source_value,
            "tv": body.target_value,
        }
        if body.properties:
            set_clause = ", ".join(
                f"r.{k} = ${k}" for k in body.properties.keys()
            )
            params.update(body.properties)

        query = (
            f"MATCH (a:`{src_label}` {{{body.source_key}: $sv}}) "
            f"MATCH (b:`{tgt_label}` {{{body.target_key}: $tv}}) "
            f"MERGE (a)-[r:`{rel}`]->(b) "
        )
        if set_clause:
            query += f"SET {set_clause} "
        query += "RETURN type(r) AS rel_type, id(r) AS edge_id"

        result = neo4j.run_query(query, params)
        neo4j.close()

        if result:
            return {"status": "created", "edge": result[0]}
        return JSONResponse({"error": "创建关系失败，请检查节点是否存在"}, status_code=404)
    except Exception as exc:
        logger.error(f"Graph create edge error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.delete("/edges")
async def delete_edge(
    source_label: str = Query(..., description="Source node label"),
    source_name: str = Query(..., description="Source node name"),
    target_label: str = Query(..., description="Target node label"),
    target_name: str = Query(..., description="Target node name"),
    rel_type: str = Query(..., description="Relationship type"),
    _auth=Depends(_verify_admin),
):
    """Delete a relationship between two nodes.

    Uses query params (REST-convention: DELETE with body is non-standard).
    """
    try:
        neo4j = _get_neo4j()
        src_label = source_label.replace("`", "")
        tgt_label = target_label.replace("`", "")
        rel = rel_type.replace("`", "")

        result = neo4j.run_query(
            f"MATCH (a:`{src_label}` {{name: $sv}})"
            f"-[r:`{rel}`]-"
            f"(b:`{tgt_label}` {{name: $tv}}) "
            f"DELETE r "
            f"RETURN count(r) AS deleted",
            {"sv": source_name, "tv": target_name},
        )
        neo4j.close()
        return {"status": "deleted", "count": result[0]["deleted"] if result else 0}
    except Exception as exc:
        logger.error(f"Graph delete edge error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/export")
async def export_graph(limit: int = Query(default=5000, ge=100, le=20000)):
    """Export graph data as JSON with pagination support.

    Args:
        limit: Max edges to export (default 5000, max 20000).
    """
    try:
        neo4j = _get_neo4j()
        nodes = neo4j.run_query(
            "MATCH (n) RETURN labels(n)[0] AS label, n.name AS name, "
            "n.category AS category, id(n) AS node_id ORDER BY label, name"
        )
        edges = neo4j.run_query(
            "MATCH (a)-[r]->(b) "
            "RETURN labels(a)[0] AS source_label, a.name AS source_name, "
            "       type(r) AS rel_type, "
            "       labels(b)[0] AS target_label, b.name AS target_name "
            "ORDER BY rel_type LIMIT $limit",
            {"limit": limit},
        )

        # Count total edges to determine if more are available
        total_edge_count = neo4j.run_query(
            "MATCH ()-[r]->() RETURN count(r) AS cnt"
        )
        total_edges = total_edge_count[0]["cnt"] if total_edge_count else 0

        neo4j.close()

        # Clean null categories
        for n in nodes:
            n["category"] = n.get("category") or ""

        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "total_edges": total_edges,
            "has_more": len(edges) < total_edges,
        }
    except Exception as exc:
        logger.error(f"Graph export error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)
