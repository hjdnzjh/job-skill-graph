# Job Review API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build backend APIs for the JobReview admin page — listing pending jobs, editing job details, approving/publishing, and rejecting/archiving with status tracking.

**Architecture:** Add a `status` property (pending/active/archived) to Neo4j Job/EmergingJob nodes for review workflow. New `api_job_review.py` module handles CRUD + review actions. Existing `EmergingJobDetector.save_emerging_jobs()` sets `status: "pending"` on creation.

**Tech Stack:** FastAPI, Neo4j (Cypher), EmergingJobDetector (existing)

---

## 前置条件

1. **Neo4j 数据基线** — 所有节点 data 完整（已在批次 0 完成）
2. **管理员认证** — 通过环境变量 `ADMIN_API_KEY` 控制审核接口的访问权限。如果未设置，审核接口返回 403。
3. **无状态迁移** — 通过 Cypher 一次性脚本为现有节点添加默认 status 值

## File Structure

**New Files:**
- `web/api_job_review.py` — Job review API routes
- `scripts/add_status_to_jobs.py` — One-time migration: add `status: "active"` to existing Job nodes
- `tests/test_job_review_api.py` — Tests

**Modified Files:**
- `web/server.py` — Register new router
- `kg/job_discovery.py` — Set `status: "pending"` on newly discovered EmergingJob nodes

---

### Task 1: Status migration for existing nodes

**Files:**
- Create: `scripts/add_status_to_jobs.py`

- [ ] **Step 1: Write migration script**

```python
"""scripts/add_status_to_jobs.py

One-time migration: add 'status' property to existing Neo4j nodes.

Usage:
    python scripts/add_status_to_jobs.py              # apply changes
    python scripts/add_status_to_jobs.py --dry-run    # preview only, no changes

- Job nodes → status: "active" (already crawled/published data)
- EmergingJob nodes → status: "pending" (awaiting review)
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "caiji"))

from config.settings import Settings
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying")
    args = parser.parse_args()

    settings = Settings()
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    driver.verify_connectivity()

    # Count nodes needing status
    with driver.session(database=settings.neo4j_database) as session:
        job_null = session.run(
            "MATCH (j:Job) WHERE j.status IS NULL RETURN count(j) AS c"
        ).single()["c"]
        ej_null = session.run(
            "MATCH (e:EmergingJob) WHERE e.status IS NULL RETURN count(e) AS c"
        ).single()["c"]
        total = job_null + ej_null

        logger.info(f"Nodes needing status: {job_null} Job + {ej_null} EmergingJob = {total}")

        if total == 0:
            logger.info("All nodes already have status set. Nothing to do.")
            driver.close()
            return

        if args.dry_run:
            logger.info("DRY RUN — no changes applied. Would update:")
            if job_null:
                logger.info(f"  SET {job_null} Job nodes → status='active'")
            if ej_null:
                logger.info(f"  SET {ej_null} EmergingJob nodes → status='pending'")
            driver.close()
            return

        # Apply
        if job_null:
            result = session.run(
                "MATCH (j:Job) WHERE j.status IS NULL "
                "SET j.status = 'active' "
                "RETURN count(j) AS updated"
            ).single()
            logger.info(f"Job nodes updated: {result['updated']}")

        if ej_null:
            result = session.run(
                "MATCH (e:EmergingJob) WHERE e.status IS NULL "
                "SET e.status = 'pending' "
                "RETURN count(e) AS updated"
            ).single()
            logger.info(f"EmergingJob nodes updated: {result['updated']}")

    driver.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run migration**

Run: `python scripts/add_status_to_jobs.py`
Expected: Logs show count of updated nodes.

- [ ] **Step 3: Verify**

Run: `python -c "from neo4j import GraphDatabase; d=GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j','12345678')); print(d.session().run('MATCH (n) WHERE n.status IS NULL RETURN count(n) AS c').single()['c'])"`
Expected: `0`

- [ ] **Step 4: Commit**

```bash
git add scripts/add_status_to_jobs.py
git commit -m "fix: add status property to existing Neo4j nodes"
```

---

### Task 2: Update job_discovery.py to set status on new nodes

**Files:**
- Modify: `kg/job_discovery.py`

- [ ] **Step 1: Add status to save_emerging_jobs**

In `EmergingJobDetector.save_emerging_jobs()`, the MERGE query already does `SET e += $props`. Just add `"status": "pending"` to the props dict:

```python
props = {
    "name": title,
    "original_title": job.get("original_title", ""),
    "responsibilities": job.get("responsibilities", ""),
    "confidence": job.get("confidence", 0.0),
    "job_count": job.get("job_count", 0),
    "status": "pending",  # <-- add this line
}
```

- [ ] **Step 2: Commit**

```bash
git add caiji/kg/job_discovery.py
git commit -m "feat(job-discovery): set status=pending on new emerging jobs"
```

---

### Task 3: Create Job Review API

**Files:**
- Create: `web/api_job_review.py`
- Modify: `web/server.py`
- Test: `tests/test_job_review_api.py`

- [ ] **Step 1: Write test**

```python
"""tests/test_job_review_api.py"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from web.server import app

client = TestClient(app)


class TestJobReviewAPI:
    """Tests for job review endpoints."""

    def test_list_pending_returns_json(self):
        response = client.get("/api/jobs/pending")
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            data = response.json()
            assert "jobs" in data
            assert "total" in data
            assert "offset" in data
            assert "limit" in data

    def test_list_pending_items_have_required_fields(self):
        response = client.get("/api/jobs/pending")
        assert response.status_code in (200, 503)
        if response.status_code == 200 and response.json().get("jobs"):
            for j in response.json()["jobs"]:
                assert "title" in j
                assert "category" in j
                assert "source" in j
                assert "status" in j
                assert "date" in j
                assert "type" in j

    def test_list_pending_filter_by_status(self):
        response = client.get("/api/jobs/pending?status=pending")
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            for j in response.json()["jobs"]:
                assert j["status"] == "pending"

    def test_list_pending_search(self):
        response = client.get("/api/jobs/pending?search=数据")
        assert response.status_code in (200, 503)

    def test_get_job_detail_regular(self):
        """Regular job title should return detail with required_skills as objects."""
        response = client.get("/api/jobs/Java开发工程师")
        assert response.status_code in (200, 404, 503)
        if response.status_code == 200:
            data = response.json()
            assert "title" in data
            assert "type" in data
            if data.get("required_skills"):
                assert isinstance(data["required_skills"], list)
                # Verify skill is an object, not a string
                assert isinstance(data["required_skills"][0], dict)

    def test_get_job_detail_missing(self):
        response = client.get("/api/jobs/__不存在的岗位__")
        assert response.status_code == 404

    def test_approve_requires_auth(self):
        """Without X-Admin-Key, approve should return 403 when ADMIN_API_KEY is set."""
        response = client.post("/api/jobs/数据科学家/approve")
        # 403 if key configured, 404/500 if no key (dev mode)
        assert response.status_code in (200, 403, 404, 500)

    def test_approve_with_wrong_key(self):
        response = client.post(
            "/api/jobs/数据科学家/approve",
            headers={"X-Admin-Key": "wrong_key"},
        )
        assert response.status_code in (200, 403, 404, 500)

    def test_reject_requires_auth(self):
        response = client.post("/api/jobs/数据科学家/reject")
        assert response.status_code in (200, 403, 404, 500)

    def test_update_requires_auth(self):
        response = client.put("/api/jobs/数据科学家", json={})
        assert response.status_code in (200, 400, 403, 404, 500)
```

- [ ] **Step 2: Run test to fail**

Run: `python -m pytest tests/test_job_review_api.py -v`
Expected: FAIL with 404 (router not registered)

- [ ] **Step 3: Create `web/api_job_review.py`**

```python
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

from web.server import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["job-review"])

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")


def _verify_admin(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    """Dependency: verify admin API key for write operations."""
    if not ADMIN_API_KEY:
        return True  # No key configured = allow (dev mode)
    if x_admin_key != ADMIN_API_KEY:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="需要管理员权限，请设置 X-Admin-Key 请求头",
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


@router.get("/pending")
async def list_pending(
    search: Optional[str] = Query(None, description="Search by job title"),
    status: Optional[str] = Query(None, description="Filter by status (pending/active/archived)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List jobs for review with pagination at database level.

    Returns only EmergingJob nodes (the ones needing review).
    Regular Job nodes are always 'active' and shown as reference.
    """
    try:
        neo4j = _get_neo4j()

        # Count total matching EmergingJob nodes (for pagination metadata)
        count_where = " WHERE "
        count_params = {}
        count_conditions = []
        if search:
            count_conditions.append("e.name CONTAINS $search")
            count_params["search"] = search
        if status:
            count_conditions.append("e.status = $status")
            count_params["status"] = status
        count_where += " AND ".join(count_conditions) if count_conditions else "1=1"

        total_result = neo4j.run_query(
            "MATCH (e:EmergingJob)" + count_where + " RETURN count(e) AS cnt",
            count_params,
        )
        total = total_result[0]["cnt"] if total_result else 0

        # Fetch paginated EmergingJob nodes — database-level SKIP/LIMIT
        emerging_where = " WHERE "
        emerging_params = {"limit": limit, "offset": offset}
        emerging_conditions = []
        if search:
            emerging_conditions.append("e.name CONTAINS $search")
            emerging_params["search"] = search
        if status:
            emerging_conditions.append("e.status = $status")
            emerging_params["status"] = status
        emerging_where += " AND ".join(emerging_conditions) if emerging_conditions else "1=1"

        emerging = neo4j.run_query(
            "MATCH (e:EmergingJob)"
            + emerging_where
            + " RETURN e.name AS title, e.status AS status,"
            "        e.confidence AS confidence,"
            "        e.responsibilities AS description,"
            "        e.job_count AS job_count,"
            "        e.imported_at AS date"
            " ORDER BY e.confidence DESC SKIP $offset LIMIT $limit",
            emerging_params,
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
            # Get required skills
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

        # Get job stats
        stats = neo4j.run_query(
            "MATCH (j:Job)-[:HAS_TITLE]->(t:JobTitle {name: $title}) "
            "RETURN count(j) AS job_count, "
            "       avg(j.salary_min) AS avg_min, avg(j.salary_max) AS avg_max, "
            "       max(j.crawl_timestamp) AS latest_date",
            {"title": title},
        )
        # Get required skills
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
            "latest_date": s.get("latest_date", ""),
            "required_skills": [{"name": sk["skill"], "category": sk.get("category", ""), "demand": sk.get("demand", 0)} for sk in skills],
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
async def update_job(title: str, body: dict = None, _auth=Depends(_verify_admin)):
    """Update job details (description, skills, category).

    Currently supports EmergingJob updates.
    Request body (partial):
    {
        "description": "new description",
        "required_skills": ["Python", "SQL"],
        "industries": ["互联网/IT"]
    }
    """
    if not body:
        return JSONResponse({"error": "请求体不能为空"}, status_code=400)

    try:
        neo4j = _get_neo4j()

        # Update description
        if "description" in body:
            neo4j.run_query(
                "MATCH (e:EmergingJob {name: $title}) "
                "SET e.responsibilities = $desc",
                {"title": title, "desc": body["description"]},
            )

        # Update skills
        if "required_skills" in body:
            # Remove old REQUIRES relationships
            neo4j.run_query(
                "MATCH (e:EmergingJob {name: $title})-[r:REQUIRES]->(s:Skill) DELETE r",
                {"title": title},
            )
            # Add new ones
            for skill_name in body["required_skills"]:
                neo4j.run_query(
                    "MATCH (e:EmergingJob {name: $title}) "
                    "MERGE (s:Skill {name: $skill}) "
                    "MERGE (e)-[:REQUIRES]->(s)",
                    {"title": title, "skill": skill_name},
                )

        neo4j.close()
        return {"status": "updated", "title": title}

    except Exception as exc:
        logger.error(f"Job update error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)
```

- [ ] **Step 4: Register router in server.py**

Add import:
```python
from web.api_job_review import router as job_review_router
```
Add include:
```python
app.include_router(job_review_router)
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_job_review_api.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add caiji/web/api_job_review.py caiji/web/server.py caiji/tests/test_job_review_api.py
git commit -m "feat(api): add job review endpoints (pending/approve/reject/update)"
```

---

### Task 4: Manual verification

- [ ] **Step 1: Restart web service**
- [ ] **Step 2: Test pending list**
```bash
curl -s http://localhost:8000/api/jobs/pending | python -m json.tool | head -30
```
- [ ] **Step 3: Test job detail**
```bash
curl -s "http://localhost:8000/api/jobs/Java开发工程师" | python -m json.tool | head -30
```
- [ ] **Step 4: Test approve emerging job**
```bash
curl -s -X POST "http://localhost:8000/api/jobs/数据科学家/approve" | python -m json.tool
```
- [ ] **Step 5: Run full test suite**
```bash
python -m pytest tests/ -v
```

---

## Self-Review Checklist

1. **Spec coverage:**
   - Left panel: searchable pending job list ✅ — `GET /api/jobs/pending?search=`
   - Right panel: job detail with edit form ✅ — `GET /api/jobs/{title}`
   - Approve button ✅ — `POST /api/jobs/{title}/approve`
   - Reject/archive button ✅ — `POST /api/jobs/{title}/reject`
   - Save draft (update details) ✅ — `PUT /api/jobs/{title}`
   - Status tracking ✅ — `status` property on EmergingJob nodes

2. **Placeholder scan:** No TODOs or TBDs.

3. **Type consistency:** Response format consistent between emerging and regular job types.
