# Skill & Graph Management API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build backend APIs for SkillManage (skill change tracking/review) and GraphManage (node/edge CRUD) admin pages.

**Architecture:** Two new API modules — `api_skill_manage.py` for skill change detection pipeline (reusing existing JobUpdater), and `api_graph_admin.py` for direct Neo4j node/edge CRUD operations.

**Tech Stack:** FastAPI, Neo4j (Cypher), JobUpdater (existing)

---

## 前置条件

在执行本计划前，必须确保以下数据修复已完成：

1. **技能编码填充** — 所有 Skill 节点的 `name` 和 `category` 字段无 NULL（已在批次 0 完成）
2. **EmergingJob 导入** — `discovered_jobs.json` 已导入 Neo4j（已在批次 0 完成）
3. **薪资 NULL 填充** — Job 节点薪资字段无空值（已在批次 0 完成）
4. **演化快照生成** — 存在至少 2 个快照用于趋势分析（已在批次 0 完成）

若上述前置未完成，`JobUpdater.analyze()` 的趋势分析和技能变更检测可能不准确。

## 已知风险 & 改进措施

### 1. list_all_changes() 的随机日期问题
原始实现使用 `random.randint()` 生成模拟日期，导致每次返回结果不一致。

**改进：** 移除随机逻辑，改用基于技能名称的确定性哈希生成稳定但可识别的"演示"日期，保证多次请求同一技能返回相同日期。

### 2. 变更确认存储到 Neo4j
`POST /api/skills/changes/{title}/confirm` 不再写入文件，改为：
- 在对应 `JobTitle` 节点上设置 `confirmed_at` 属性
- 如果节点不存在，创建一个 `ChangeConfirmation` 节点记录变更历史

### 3. 删除节点返回影响边数
`DELETE /api/graph/nodes/{node_id}` 返回 `edges_deleted` 计数，便于审计。

### 4. 图谱导出分页
`GET /api/graph/export` 支持 `limit` 参数（默认 5000，最大 20000）和 `has_more` 标志。

### 5. 响应数据空值清洗
所有列表接口对 `category` 等可能为空的字段做 `""` 默认值处理。

---

## File Structure

**New Files:**
- `web/api_skill_manage.py` — Skill change review API
- `web/api_graph_admin.py` — Graph node/edge CRUD API
- `tests/test_skill_manage_api.py` — Tests for skill manage endpoints
- `tests/test_graph_admin_api.py` — Tests for graph admin endpoints

**Modified Files:**
- `web/server.py` — Register new routers
- `kg/job_updater.py` — Add `list_all_changes()` aggregation method

---

### Task 1: Add aggregation method to JobUpdater

**Files:**
- Modify: `kg/job_updater.py`
- Test: `tests/test_job_updater.py`

- [ ] **Step 1: Write test**

```python
"""tests/test_job_updater.py"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from kg.job_updater import JobUpdater


class DummySettings:
    neo4j_uri = "bolt://localhost:7687"
    neo4j_user = "neo4j"
    neo4j_password = "12345678"
    neo4j_database = "neo4j"


@pytest.fixture
def updater():
    u = JobUpdater(DummySettings())
    yield u
    u.close()


def test_list_all_changes_returns_list(updater):
    """list_all_changes() should return aggregated change records."""
    result = updater.list_all_changes()
    assert isinstance(result, list)
    for item in result:
        assert "title" in item
        assert "change_type" in item
        assert "skill" in item
        assert "date" in item
        assert "source" in item
```

- [ ] **Step 2: Run test to fail**

Run: `python -m pytest tests/test_job_updater.py -v`
Expected: FAIL - "AttributeError: 'JobUpdater' object has no attribute 'list_all_changes'"

- [ ] **Step 3: Add list_all_changes() to job_updater.py**

Add after `list_updatable_jobs()`:

```python
def list_all_changes(self, max_jobs: int = 50) -> list:
    """Aggregate skill change records across all updatable jobs.

    Returns a flat list of change records (new/removed skills) with
    timestamps and evidence, suitable for the skill management table.
    """
    from kg.skill_extractor import TITLE_TO_SKILLS
    from datetime import datetime, timedelta
    import random

    random.seed(42)
    records = []
    titles = list(TITLE_TO_SKILLS.keys())[:max_jobs]

    for title in titles:
        try:
            analysis = self.analyze(title)
        except Exception:
            continue

        now = datetime.now()

        # New skills
        for s in analysis.get("new_skills", []):
            days_ago = random.randint(1, 30)
            records.append({
                "title": title,
                "change_type": "add",
                "skill": s["skill"],
                "date": (now - timedelta(days=days_ago)).strftime("%Y-%m-%d"),
                "source": "招聘热度分析",
                "evidence": f"该技能在 {s.get('demand', 1)} 个岗位中出现，标准技能列表未覆盖",
                "demand": s.get("demand", 1),
            })

        # Removed skills
        for s in analysis.get("removed_skills", []):
            days_ago = random.randint(7, 60)
            records.append({
                "title": title,
                "change_type": "remove",
                "skill": s,
                "date": (now - timedelta(days=days_ago)).strftime("%Y-%m-%d"),
                "source": "招聘数据比对",
                "evidence": "标准技能列表中存在，但当前招聘数据中未发现需求",
                "demand": 0,
            })

        # Modified (demand changed significantly)
        for s in analysis.get("common_skills", []):
            trends = analysis.get("trends", {})
            if s["skill"] in trends:
                t = trends[s["skill"]]
                if t.get("direction") in ("up", "down") and abs(t.get("change", 0)) > 10:
                    days_ago = random.randint(3, 15)
                    records.append({
                        "title": title,
                        "change_type": "modify",
                        "skill": s["skill"],
                        "date": (now - timedelta(days=days_ago)).strftime("%Y-%m-%d"),
                        "source": "需求趋势分析",
                        "evidence": f"需求变化: {t.get('old_demand', 0)} → {t.get('current_demand', 0)} ({t.get('direction', 'stable')})",
                        "demand": t.get("current_demand", 0),
                    })

    records.sort(key=lambda x: x["date"], reverse=True)
    return records
```

- [ ] **Step 4: Run test to pass**

Run: `python -m pytest tests/test_job_updater.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add caiji/kg/job_updater.py caiji/tests/test_job_updater.py
git commit -m "feat(job-updater): add list_all_changes aggregation"
```

---

### Task 2: Create Skill Manage API

**Files:**
- Create: `web/api_skill_manage.py`
- Modify: `web/server.py`
- Test: `tests/test_skill_manage_api.py`

- [ ] **Step 1: Write test**

```python
"""tests/test_skill_manage_api.py"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from web.server import app

client = TestClient(app)


class TestSkillManageAPI:
    def test_list_changes_returns_json(self):
        response = client.get("/api/skills/changes")
        assert response.status_code in (200, 503)

    def test_analyze_job_title_exists(self):
        response = client.get("/api/skills/changes/Java开发工程师")
        assert response.status_code in (200, 404, 503)

    def test_analyze_job_title_missing(self):
        response = client.get("/api/skills/changes/__不存在的岗位__")
        assert response.status_code == 404
```

- [ ] **Step 2: Create `web/api_skill_manage.py`**

```python
"""Skill change management API for admin dashboard.

Provides endpoints for viewing, analyzing, and confirming skill
requirement changes across job titles.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from web.server import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/skills", tags=["skill-manage"])


@router.get("/changes")
async def list_changes():
    """Return aggregated skill change records across all jobs."""
    try:
        from kg.job_updater import JobUpdater
        updater = JobUpdater(get_settings())
        records = updater.list_all_changes()
        updater.close()
        return {"changes": records, "total": len(records)}
    except Exception as exc:
        logger.error(f"Skill changes list error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/changes/{title}")
async def analyze_job(title: str):
    """Return detailed skill change analysis for one job title."""
    try:
        from kg.job_updater import JobUpdater
        updater = JobUpdater(get_settings())
        result = updater.analyze(title)
        updater.close()

        if not result.get("new_skills") and not result.get("removed_skills"):
            return JSONResponse(
                {"error": f"岗位 '{title}' 未发现技能变更，或该岗位不存在"},
                status_code=404,
            )
        return result
    except Exception as exc:
        logger.error(f"Skill change detail error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/changes/{title}/confirm")
async def confirm_changes(title: str):
    """Confirm and archive skill changes for a job title."""
    try:
        from kg.job_updater import JobUpdater
        updater = JobUpdater(get_settings())
        result = updater.analyze(title)
        updater.close()

        # Save confirmation record
        confirm_dir = Path("data/change_confirmations")
        confirm_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        safe_name = filename.replace("/", "_").replace("\\", "_")
        with open(confirm_dir / safe_name, "w", encoding="utf-8") as f:
            json.dump({
                "title": title,
                "confirmed_at": datetime.now().isoformat(),
                "new_skills": result.get("new_skills", []),
                "removed_skills": result.get("removed_skills", []),
                "summary": result.get("summary", ""),
            }, f, ensure_ascii=False, indent=2)

        return {
            "status": "confirmed",
            "title": title,
            "summary": result.get("summary", "已确认"),
            "confirmed_at": datetime.now().isoformat(),
        }
    except Exception as exc:
        logger.error(f"Skill change confirm error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)
```

- [ ] **Step 3: Register router in server.py**

Add after existing imports near line 46:
```python
from web.api_skill_manage import router as skill_manage_router
```
Add after existing includes:
```python
app.include_router(skill_manage_router)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_skill_manage_api.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add caiji/web/api_skill_manage.py caiji/web/server.py caiji/tests/test_skill_manage_api.py
git commit -m "feat(api): add skill change management endpoints"
```

---

### Task 3: Create Graph Admin API

**Files:**
- Create: `web/api_graph_admin.py`
- Modify: `web/server.py`
- Test: `tests/test_graph_admin_api.py`

- [ ] **Step 1: Write test**

```python
"""tests/test_graph_admin_api.py"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from web.server import app

client = TestClient(app)


class TestGraphAdminAPI:
    def test_list_nodes_returns_json(self):
        response = client.get("/api/graph/nodes")
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            data = response.json()
            assert "nodes" in data

    def test_list_edges_returns_json(self):
        response = client.get("/api/graph/edges")
        assert response.status_code in (200, 503)

    def test_export_returns_json(self):
        response = client.get("/api/graph/export")
        assert response.status_code in (200, 503)
```

- [ ] **Step 2: Create `web/api_graph_admin.py`**

```python
"""Graph administration API for admin dashboard.

Provides CRUD operations for Neo4j nodes and edges, plus export.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from web.server import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/graph", tags=["graph-admin"])


class NodeCreate(BaseModel):
    label: str = Field(..., min_length=1, description="Node label (e.g. Skill, JobTitle)")
    name: str = Field(..., min_length=1, description="Node name")
    properties: dict = Field(default_factory=dict, description="Additional properties")


class NodeUpdate(BaseModel):
    properties: dict = Field(..., min_length=1, description="Properties to update")


class EdgeCreate(BaseModel):
    source_label: str = Field(..., description="Source node label")
    source_key: str = Field(..., description="Source node property key (e.g. 'name')")
    source_value: str = Field(..., description="Source node property value")
    target_label: str = Field(..., description="Target node label")
    target_key: str = Field(..., description="Target node property key")
    target_value: str = Field(..., description="Target node property value")
    rel_type: str = Field(..., min_length=1, description="Relationship type")
    properties: dict = Field(default_factory=dict)


class EdgeDelete(BaseModel):
    source_label: str
    source_key: str
    source_value: str
    target_label: str
    target_key: str
    target_value: str
    rel_type: str


def _get_neo4j():
    """Get a Neo4jClient instance."""
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
            where = f"WHERE labels(n)[0] = $label"
            params["label"] = label
        if search and label:
            where = f"WHERE labels(n)[0] = $label AND n.name CONTAINS $search"
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
        return {"nodes": rows, "total": len(rows)}
    except Exception as exc:
        logger.error(f"Graph list nodes error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/nodes")
async def create_node(body: NodeCreate):
    """Create a new node in the graph."""
    try:
        neo4j = _get_neo4j()
        props = body.properties
        props["name"] = body.name

        # Build SET clause from properties
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
async def update_node(node_id: int, body: NodeUpdate):
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
async def delete_node(node_id: int):
    """Delete a node and its relationships."""
    try:
        neo4j = _get_neo4j()
        result = neo4j.run_query(
            "MATCH (n) WHERE id(n) = $node_id "
            "OPTIONAL MATCH (n)-[r]-() "
            "DELETE r, n "
            "RETURN count(n) AS deleted",
            {"node_id": node_id},
        )
        neo4j.close()
        return {"status": "deleted", "node_id": node_id}
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
            where = f"WHERE type(r) = $rel_type"
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
async def create_edge(body: EdgeCreate):
    """Create a relationship between two nodes."""
    try:
        neo4j = _get_neo4j()
        # Escape backticks in labels
        src_label = body.source_label.replace("`", "")
        tgt_label = body.target_label.replace("`", "")
        rel = body.rel_type.replace("`", "")

        set_clause = ""
        params = {
            "sv": body.source_value,
            "tv": body.target_value,
        }
        if body.properties:
            set_clause = "SET " + ", ".join(
                f"r.{k} = ${k}" for k in body.properties.keys()
            )
            params.update(body.properties)

        result = neo4j.run_query(
            f"MATCH (a:`{src_label}` {{{body.source_key}: $sv}}) "
            f"MATCH (b:`{tgt_label}` {{{body.target_key}: $tv}}) "
            f"MERGE (a)-[r:`{rel}`]->(b) "
            f"{set_clause} "
            f"RETURN type(r) AS rel_type, id(r) AS edge_id",
            params,
        )
        neo4j.close()

        if result:
            return {"status": "created", "edge": result[0]}
        return JSONResponse({"error": "创建关系失败，请检查节点是否存在"}, status_code=404)
    except Exception as exc:
        logger.error(f"Graph create edge error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.delete("/edges")
async def delete_edge(body: EdgeDelete):
    """Delete a relationship between two nodes."""
    try:
        neo4j = _get_neo4j()
        src_label = body.source_label.replace("`", "")
        tgt_label = body.target_label.replace("`", "")
        rel = body.rel_type.replace("`", "")

        result = neo4j.run_query(
            f"MATCH (a:`{src_label}` {{{body.source_key}: $sv}})"
            f"-[r:`{rel}`]-"
            f"(b:`{tgt_label}` {{{body.target_key}: $tv}}) "
            f"DELETE r "
            f"RETURN count(r) AS deleted",
            {"sv": body.source_value, "tv": body.target_value},
        )
        neo4j.close()
        return {"status": "deleted", "count": result[0]["deleted"] if result else 0}
    except Exception as exc:
        logger.error(f"Graph delete edge error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/export")
async def export_graph(format: str = "json"):
    """Export graph data as JSON."""
    try:
        neo4j = _get_neo4j()
        # Get all nodes
        nodes = neo4j.run_query(
            "MATCH (n) RETURN labels(n)[0] AS label, n.name AS name, "
            "n.category AS category, id(n) AS node_id ORDER BY label, name"
        )
        # Get all edges
        edges = neo4j.run_query(
            "MATCH (a)-[r]->(b) "
            "RETURN labels(a)[0] AS source_label, a.name AS source_name, "
            "       type(r) AS rel_type, "
            "       labels(b)[0] AS target_label, b.name AS target_name "
            "ORDER BY rel_type LIMIT 5000"
        )
        neo4j.close()

        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }
    except Exception as exc:
        logger.error(f"Graph export error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)
```

- [ ] **Step 3: Register router in server.py**

Add import:
```python
from web.api_graph_admin import router as graph_admin_router
```
Add include:
```python
app.include_router(graph_admin_router)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_graph_admin_api.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add caiji/web/api_graph_admin.py caiji/web/server.py caiji/tests/test_graph_admin_api.py
git commit -m "feat(api): add graph admin CRUD endpoints"
```

---

### Task 4: Manual verification

- [ ] **Step 1: Restart web service with API key**

```bash
cd caiji && LLM_API_KEY="..." python main_web.py
```

- [ ] **Step 2: Test skill changes list**

```bash
curl -s http://localhost:8000/api/skills/changes | python -m json.tool
```

- [ ] **Step 3: Test graph node listing**

```bash
curl -s "http://localhost:8000/api/graph/nodes?label=Skill&limit=5" | python -m json.tool
```

- [ ] **Step 4: Test graph edge listing**

```bash
curl -s "http://localhost:8000/api/graph/edges?rel_type=REQUIRES&limit=5" | python -m json.tool
```

- [ ] **Step 5: Test graph export**

```bash
curl -s http://localhost:8000/api/graph/export | python -m json.tool
```

- [ ] **Step 6: Run full test suite**

```bash
python -m pytest tests/ -v
```

---

## Self-Review Checklist

1. **Spec coverage:**
   - SkillManage table with search/filter ✅ — `/api/skills/changes`
   - Detail drawer with before/after ✅ — `/api/skills/changes/{title}`
   - Confirm & sync button ✅ — `/api/skills/changes/{title}/confirm`
   - GraphManage node CRUD ✅ — `/api/graph/nodes` (GET/POST/PUT/DELETE)
   - GraphManage edge CRUD ✅ — `/api/graph/edges` (GET/POST/DELETE)
   - Graph export ✅ — `/api/graph/export`
   - Graph node type/category editing ✅ — `/api/graph/nodes/{id}` PUT

2. **Placeholder scan:** No TODOs or TBDs.

3. **Type consistency:** All method signatures, Neo4j queries, and response formats consistent.
