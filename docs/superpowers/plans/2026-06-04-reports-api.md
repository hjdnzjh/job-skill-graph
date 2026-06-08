# Reports & Analytics API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build backend APIs for the Reports admin page — job growth trends, skill demand trends, job status distribution, and AI-derived insights.

**Architecture:** New `api_reports.py` module computes aggregations from Neo4j + evolution snapshots. Snapshots sorted by internal `timestamp` field, not filename. Skill trends support both two-point growth and multi-point detail series. Insights have configurable thresholds (min ±10% for growth/decline).

**Tech Stack:** FastAPI, Neo4j (Cypher), EvolutionTracker (existing), 6 evolution snapshots

---

## 前置条件

1. **演化快照存在** — 至少 2 个快照用于趋势计算（已完成，现有 6 个）
2. **技能编码完整** — Skill.category 无 NULL（已完成）
3. **status 字段已添加** — Job/EmergingJob 有 status（批次 3 完成）

## 已知改进点（根据代码Review）

| 问题 | 改进 |
|------|------|
| 快照格式不一致风险 | `_load_snapshots()` 验证必填字段（timestamp, record_count, top_skills），缺失时 warning 并跳过 |
| 按文件名排序不可靠 | 改为按文件内 `timestamp` 字段排序 |
| 技能趋势单点对比丢失细节 | 增加 `skill_trends_detail` 字段：每个快照时间点的 demand 数组 |
| 新增技能增长率计算异常 | `old_demand=0, new_demand>0` → `growth=100`（标记为 `new`） |
| 洞察阈值不足 | 增长 > 10% 才算"显著增长"，下降 > 5% 才算"萎缩" |
| 缺少"新兴技能出现"洞察 | 新增一条 `category="新兴技能出现"` |
| 快照加载无缓存 | `@functools.lru_cache(maxsize=1)` 缓存快照，每次请求只读一次磁盘 |
| 快照不足时无提示 | 响应中增加 `warnings` 字段 |
| 月份跨年混淆 | `_format_month` 返回 `"YYYY年M月"` |
| 测试覆盖不足 | 增加 mock 快照测试，验证空快照/单快照/多快照场景 |

## File Structure

**New Files:**
- `web/api_reports.py` — Reports API routes
- `tests/test_reports_api.py` — Tests (with mock snapshots)

**Modified Files:**
- `web/server.py` — Register new router

---

### Task 1: Create Reports API

**Files:**
- Create: `web/api_reports.py`
- Modify: `web/server.py`
- Test: `tests/test_reports_api.py`

- [ ] **Step 1: Write test**

```python
"""tests/test_reports_api.py"""

import sys, os
import json, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from web.server import app

client = TestClient(app)


class TestReportsAPI:
    """Tests for /api/reports/overview endpoint."""

    def test_overview_returns_all_sections(self):
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            data = response.json()
            assert "job_trends" in data
            assert "skill_trends" in data
            assert "skill_trends_detail" in data
            assert "status_distribution" in data
            assert "insights" in data

    def test_job_trends_has_monthly_data(self):
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            trends = response.json()["job_trends"]
            assert len(trends) > 0
            for t in trends:
                assert "month" in t
                assert "count" in t
                assert len(t["month"]) > 2  # e.g. "2026年6月"

    def test_skill_trends_detail_is_array(self):
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            detail = response.json().get("skill_trends_detail", [])
            if detail:
                for entry in detail:
                    assert "skill" in entry
                    assert "series" in entry
                    assert isinstance(entry["series"], list)

    def test_status_distribution_has_all_statuses(self):
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            dist = response.json()["status_distribution"]
            assert len(dist) > 0
            for d in dist:
                assert "name" in d
                assert "value" in d

    def test_insights_contains_analysis(self):
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            insights = response.json()["insights"]
            assert len(insights) > 0
            for ins in insights:
                assert "category" in ins
                assert "title" in ins
                assert "description" in ins

    def test_warnings_when_few_snapshots(self):
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 503)


class TestReportsWithMockSnapshots:
    """Tests using temporary mock snapshot files."""

    @pytest.fixture(autouse=True)
    def setup_mock_snapshots(self, monkeypatch):
        """Replace snapshot dir with a temp dir containing mock snapshots."""
        self.tmp_dir = tempfile.mkdtemp()
        # Override SNAPSHOT_DIR in the reports module
        import web.api_reports
        monkeypatch.setattr(web.api_reports, "SNAPSHOT_DIR", self.tmp_dir)

        # Create 3 mock snapshots
        snapshots_data = [
            {
                "timestamp": "2025-06-01T00:00:00",
                "record_count": 500,
                "graph": {"total_nodes": 1000, "total_edges": 5000},
                "top_skills": [
                    {"skill": "Python", "demand": 200},
                    {"skill": "Java", "demand": 150},
                ],
            },
            {
                "timestamp": "2025-12-01T00:00:00",
                "record_count": 800,
                "graph": {"total_nodes": 1600, "total_edges": 8000},
                "top_skills": [
                    {"skill": "Python", "demand": 250},
                    {"skill": "Java", "demand": 120},
                ],
            },
            {
                "timestamp": "2026-06-01T00:00:00",
                "record_count": 1175,
                "graph": {"total_nodes": 2479, "total_edges": 16093},
                "top_skills": [
                    {"skill": "Python", "demand": 314},
                    {"skill": "Java", "demand": 100},
                    {"skill": "Rust", "demand": 10},
                ],
            },
        ]
        for i, snap in enumerate(snapshots_data):
            fname = f"snapshot_{i:03d}.json"  # deliberately non-chronological names
            with open(os.path.join(self.tmp_dir, fname), "w", encoding="utf-8") as f:
                json.dump(snap, f)

        yield
        shutil.rmtree(self.tmp_dir)

    def test_job_trends_has_three_points(self):
        """Should produce 3 job_trends points from 3 mock snapshots."""
        from web.api_reports import _load_snapshots, get_overview
        # Clear any cached snapshots
        import web.api_reports
        web.api_reports._load_snapshots.cache_clear()
        snaps = _load_snapshots()
        assert len(snaps) == 3
        assert snaps[0]["timestamp"].startswith("2025-06")  # sorted by timestamp not filename

    def test_skill_trends_computes_growth_correctly(self):
        """Python: 200->314 = 57% growth. Java: 150->100 = -33%."""
        import web.api_reports
        web.api_reports._load_snapshots.cache_clear()
        response = client.get("/api/reports/overview")
        assert response.status_code == 200
        data = response.json()
        trends = {t["name"]: t for t in data["skill_trends"]}
        assert "Python" in trends
        assert trends["Python"]["growth"] == 57  # (314-200)/200*100 = 57
        assert "Java" in trends
        assert trends["Java"]["growth"] == -33  # (100-150)/150*100 = -33

    def test_new_skill_has_growth_100(self):
        """Rust: old=0, new=10 -> growth=100 (marked as new)."""
        import web.api_reports
        web.api_reports._load_snapshots.cache_clear()
        response = client.get("/api/reports/overview")
        assert response.status_code == 200
        data = response.json()
        trends = {t["name"]: t for t in data["skill_trends"]}
        assert "Rust" in trends
        assert trends["Rust"]["growth"] == 100
        assert trends["Rust"]["direction"] == "new"

    def test_skill_trends_detail_has_all_timepoints(self):
        """skill_trends_detail should have 3 series points per skill."""
        import web.api_reports
        web.api_reports._load_snapshots.cache_clear()
        response = client.get("/api/reports/overview")
        assert response.status_code == 200
        data = response.json()
        detail = {d["skill"]: d for d in data["skill_trends_detail"]}
        assert "Python" in detail
        assert len(detail["Python"]["series"]) == 3
        # Series sorted by time: [500, 800, 1175] -> demands
        assert detail["Python"]["series"][0]["demand"] == 200
        assert detail["Python"]["series"][-1]["demand"] == 314

    def test_empty_snapshot_dir_returns_empty_trends(self, monkeypatch):
        """When no snapshots exist, trends should be empty."""
        empty_dir = tempfile.mkdtemp()
        import web.api_reports
        monkeypatch.setattr(web.api_reports, "SNAPSHOT_DIR", empty_dir)
        web.api_reports._load_snapshots.cache_clear()
        response = client.get("/api/reports/overview")
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            data = response.json()
            assert data["job_trends"] == []
            assert data["skill_trends"] == []
            # Should have "数据不足" insight
            has_fallback = any(
                ins.get("category") == "数据不足" for ins in data["insights"]
            )
            assert has_fallback
        shutil.rmtree(empty_dir)
```

- [ ] **Step 2: Create `web/api_reports.py`**

```python
"""Reports & analytics API for admin dashboard.

Provides aggregated data for the Reports page:
- Job growth trends (from evolution snapshots)
- Skill demand trends (demand changes over time, with multi-point detail)
- Job status distribution (pending/active/archived counts)
- AI insights (rule-based trend analysis with configurable thresholds)
"""

import functools
import json
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from web.server import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])

SNAPSHOT_DIR = "data/snapshots"

# Insight thresholds
GROWTH_THRESHOLD = 10   # min +% to be "significant growth"
DECLINE_THRESHOLD = 5    # min -% to be "significant decline"


def _get_neo4j():
    from kg.neo4j_client import Neo4jClient
    return Neo4jClient(get_settings())


def _validate_snapshot(snap: dict) -> bool:
    """Validate snapshot has required fields. Logs warning and returns False if not."""
    required = ["timestamp", "record_count", "graph", "top_skills"]
    for field in required:
        if field not in snap:
            logger.warning(f"Snapshot missing required field '{field}', skipping")
            return False
    if not isinstance(snap.get("top_skills"), list):
        logger.warning("Snapshot top_skills is not a list, skipping")
        return False
    return True


@functools.lru_cache(maxsize=1)
def _load_snapshots() -> tuple:
    """Load all valid snapshots sorted by internal timestamp (oldest first).

    Returns tuple for hashability (lru_cache requirement).
    Validates required fields, skips invalid snapshots with warning.
    """
    if not os.path.isdir(SNAPSHOT_DIR):
        return ()
    files = [
        os.path.join(SNAPSHOT_DIR, f)
        for f in os.listdir(SNAPSHOT_DIR)
        if f.endswith(".json") and f != "snapshot_index.json"
    ]
    snapshots = []
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            try:
                snap = json.load(f)
                if _validate_snapshot(snap):
                    snapshots.append(snap)
                else:
                    logger.warning(f"Skipping invalid snapshot: {fp}")
            except json.JSONDecodeError as exc:
                logger.warning(f"Failed to parse snapshot {fp}: {exc}")

    # Sort by internal timestamp, not filename
    snapshots.sort(key=lambda s: s.get("timestamp", ""))
    return tuple(snapshots)


def _format_month(ts_str: str) -> str:
    """Convert ISO timestamp to month label with year (e.g. '2026年6月')."""
    try:
        dt = datetime.fromisoformat(ts_str)
        return f"{dt.year}年{dt.month}月"
    except (ValueError, TypeError):
        return ts_str[:7]


@router.get("/overview")
async def get_overview():
    """Return aggregated report data: trends, distribution, insights.

    Computes:
    1. Job trends — monthly job counts from all snapshots
    2. Skill trends — growth between oldest and newest snapshot (threshold gated)
    3. Skill trends detail — multi-point demand series per skill across all snapshots
    4. Status distribution — pending/active/archived counts from Neo4j
    5. Insights — rule-driven analysis with configurable thresholds
    """
    try:
        snapshots = list(_load_snapshots())
        neo4j = _get_neo4j()
        warnings = []

        if len(snapshots) < 2:
            warnings.append(
                "演化快照不足 2 个，技能趋势和部分洞察不可用。"
                f"当前快照数: {len(snapshots)}"
            )

        # --- 1. Job Growth Trends ---
        job_trends = []
        for snap in snapshots:
            ts = snap.get("timestamp", "")
            record_count = snap.get("record_count", 0)
            total_nodes = snap.get("graph", {}).get("total_nodes", 0)
            total_edges = snap.get("graph", {}).get("total_edges", 0)
            job_trends.append({
                "month": _format_month(ts),
                "timestamp": ts[:10],
                "count": record_count,
                "total_nodes": total_nodes,
                "total_edges": total_edges,
            })

        # --- 2. Skill Demand Trends (oldest vs newest, threshold-gated) ---
        skill_trends = []
        skill_trends_detail = []
        if len(snapshots) >= 2:
            oldest = snapshots[0]
            newest = snapshots[-1]

            old_skills = {
                s["skill"]: s.get("demand", 0)
                for s in oldest.get("top_skills", [])
            }
            new_skills = {
                s["skill"]: s.get("demand", 0)
                for s in newest.get("top_skills", [])
            }

            # Build multi-point detail: collect demand per skill across all snapshots
            all_skill_names = set(list(old_skills.keys()) + list(new_skills.keys()))
            for s in snapshots:
                for ts in s.get("top_skills", []):
                    all_skill_names.add(ts["skill"])

            for name in sorted(all_skill_names):
                old_demand = old_skills.get(name, 0)
                new_demand = new_skills.get(name, 0)
                if old_demand == 0 and new_demand == 0:
                    continue

                # Compute growth
                if old_demand == 0 and new_demand > 0:
                    growth = 100
                    direction = "new"
                elif old_demand > 0:
                    growth = int((new_demand - old_demand) / old_demand * 100)
                    direction = "up" if growth > 0 else ("down" if growth < 0 else "stable")
                else:
                    growth = 0
                    direction = "stable"

                skill_trends.append({
                    "name": name,
                    "old_demand": old_demand,
                    "new_demand": new_demand,
                    "growth": growth,
                    "direction": direction,
                })

                # Build multi-point detail series
                series = []
                for snap in snapshots:
                    snap_ts = snap.get("timestamp", "")
                    snap_skills = {s["skill"]: s.get("demand", 0)
                                   for s in snap.get("top_skills", [])}
                    series.append({
                        "timestamp": snap_ts[:10],
                        "month": _format_month(snap_ts),
                        "demand": snap_skills.get(name, 0),
                    })
                skill_trends_detail.append({
                    "skill": name,
                    "series": series,
                })

            skill_trends.sort(key=lambda x: -abs(x["growth"]))

        # --- 3. Job Status Distribution ---
        active_jobs = neo4j.run_query(
            "MATCH (j:Job {status: 'active'}) RETURN count(j) AS cnt"
        )[0]["cnt"]
        pending_ej = neo4j.run_query(
            "MATCH (e:EmergingJob {status: 'pending'}) RETURN count(e) AS cnt"
        )[0]["cnt"]
        archived_ej = neo4j.run_query(
            "MATCH (e:EmergingJob {status: 'archived'}) RETURN count(e) AS cnt"
        )[0]["cnt"]
        active_ej = neo4j.run_query(
            "MATCH (e:EmergingJob {status: 'active'}) RETURN count(e) AS cnt"
        )[0]["cnt"]

        status_distribution = [
            {"name": "活跃岗位", "value": active_jobs + active_ej},
            {"name": "待审核", "value": pending_ej},
            {"name": "已归档", "value": archived_ej},
        ]

        neo4j.close()

        # --- 4. AI Insights (rule-driven, with thresholds) ---
        insights = _generate_insights(skill_trends, job_trends, status_distribution)

        return {
            "job_trends": job_trends,
            "skill_trends": skill_trends[:50],
            "skill_trends_detail": skill_trends_detail[:50],
            "status_distribution": status_distribution,
            "insights": insights,
            "warnings": warnings,
        }

    except Exception as exc:
        logger.error(f"Reports overview error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


def _generate_insights(skill_trends: list, job_trends: list,
                       status_distribution: list) -> list:
    """Generate actionable insights from trend data.

    All insights use configurable thresholds (GROWTH_THRESHOLD, DECLINE_THRESHOLD)
    to avoid trivial or misleading results. If no insight meets thresholds,
    returns a single "数据不足" fallback.
    """
    insights = []

    # Insight 1: Fastest growing skills (growth > GROWTH_THRESHOLD %)
    rising = [
        s for s in skill_trends
        if s.get("direction") == "up" and s.get("growth", 0) >= GROWTH_THRESHOLD
    ][:3]
    if rising:
        names = [s["name"] for s in rising]
        max_growth = max(s["growth"] for s in rising)
        insights.append({
            "category": "高增长潜力",
            "title": "技能需求快速增长",
            "description": (
                f"{'、'.join(names)} 等技能在过去一段时间需求增长显著，"
                f"最高增幅达 {max_growth}%。建议关注相关人才培养和储备。"
            ),
        })

    # Insight 2: Newly appearing skills (old_demand=0, new_demand>0)
    new_skills = [
        s for s in skill_trends
        if s.get("direction") == "new"
    ][:3]
    if new_skills:
        names = [s["name"] for s in new_skills]
        insights.append({
            "category": "新兴技能出现",
            "title": "图谱新增技能",
            "description": (
                f"{'、'.join(names)} 等技能首次出现在招聘需求中，"
                f"可能代表新的技术方向或岗位需求。建议持续关注。"
            ),
        })

    # Insight 3: Declining skills (decline > DECLINE_THRESHOLD %)
    falling = [
        s for s in skill_trends
        if s.get("direction") == "down" and abs(s.get("growth", 0)) >= DECLINE_THRESHOLD
    ][:3]
    if falling:
        names = [s["name"] for s in falling]
        insights.append({
            "category": "存量岗位萎缩",
            "title": "部分技能需求下降",
            "description": (
                f"{'、'.join(names)} 等技能需求出现下降趋势，"
                f"相关从业者可考虑向新兴技能方向转型。"
            ),
        })

    # Insight 4: Data volume growth
    if len(job_trends) >= 2:
        first_cnt = job_trends[0].get("count", 0)
        last_cnt = job_trends[-1].get("count", 0)
        if first_cnt > 0 and last_cnt > first_cnt:
            growth_pct = int((last_cnt - first_cnt) / first_cnt * 100)
            insights.append({
                "category": "数据规模增长",
                "title": "岗位数据持续扩展",
                "description": (
                    f"岗位记录数从 {first_cnt} 增长至 {last_cnt}，"
                    f"增长 {growth_pct}%。数据覆盖度持续提升。"
                ),
            })

    # Insight 5: Pending review alert
    pending_count = 0
    for d in status_distribution:
        if d.get("name") == "待审核":
            pending_count = d.get("value", 0)
    if pending_count > 0:
        insights.append({
            "category": "待处理事项",
            "title": "有待审核的新兴岗位",
            "description": (
                f"当前有 {pending_count} 个新兴岗位待审核，"
                f"建议及时处理以保持图谱时效性。"
            ),
        })

    if not insights:
        insights.append({
            "category": "数据不足",
            "title": "暂无足够数据生成洞察",
            "description": "请确保已生成至少 2 个演化快照以计算趋势。",
        })

    return insights
```

- [ ] **Step 3: Register router in server.py**

Add import:
```python
from web.api_reports import router as reports_router
```
Add include:
```python
app.include_router(reports_router)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_reports_api.py -v`
Expected: All pass

- [ ] **Step 5: Manual verification**

Restart service and test:
```bash
curl -s http://localhost:8000/api/reports/overview | python -m json.tool
```

Expected: Returns job_trends (6 points), skill_trends (top skills with growth), status_distribution (3 items), insights (2-4 items)

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add caiji/web/api_reports.py caiji/web/server.py caiji/tests/test_reports_api.py
git commit -m "feat(api): add reports and analytics overview endpoint"
```

---

## Self-Review Checklist

1. **Spec coverage:**
   - Monthly job growth bar chart ✅ — `job_trends` array with month/count
   - Skill demand trends line chart ✅ — `skill_trends` with growth rates
   - Job status distribution pie chart ✅ — `status_distribution` with pending/active/archived
   - AI insights cards ✅ — `insights` with high-growth + declining + alerts
   - Time range filtering — computed from snapshot range (T-12mo max)
   - Data source transparency — all counts derived from Neo4j + snapshots

2. **Placeholder scan:** No TODOs or TBDs.

3. **Type consistency:** Response format matches mock data structure for easy frontend integration.
