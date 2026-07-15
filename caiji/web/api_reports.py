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

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from web._settings import get_settings

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
    """Validate snapshot has required fields."""
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
    """Return aggregated report data: trends, distribution, insights."""
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

        # --- 2. Skill Demand Trends + Detail ---
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

            # Build full skill set across all snapshots
            all_skill_names = set()
            for s in snapshots:
                for ts_entry in s.get("top_skills", []):
                    all_skill_names.add(ts_entry["skill"])

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

                # Multi-point detail series
                series = []
                for snap in snapshots:
                    snap_ts = snap.get("timestamp", "")
                    snap_skills = {
                        s["skill"]: s.get("demand", 0)
                        for s in snap.get("top_skills", [])
                    }
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

        # --- 3. Job Status Distribution (graceful if Neo4j unavailable) ---
        status_distribution = []
        try:
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
        except Exception as neo4j_err:
            logger.warning(f"Neo4j unavailable for status distribution: {neo4j_err}")
            status_distribution = [
                {"name": "活跃岗位", "value": 0},
                {"name": "待审核", "value": 0},
                {"name": "已归档", "value": 0},
            ]

        neo4j.close()

        # --- 4. Domain trends ---
        domain_trends = []
        if len(snapshots) >= 2:
            oldest = snapshots[0]
            newest = snapshots[-1]

            old_domains = {}
            for d in oldest.get("skills_by_domain", []):
                old_domains[d.get("domain")] = d
            new_domains = {}
            for d in newest.get("skills_by_domain", []):
                new_domains[d.get("domain")] = d

            all_domains = set(list(old_domains.keys()) + list(new_domains.keys()))
            for domain_code in all_domains:
                od = old_domains.get(domain_code, {"demand": 0, "skill_count": 0, "domain_name": ""})
                nd = new_domains.get(domain_code, {"demand": 0, "skill_count": 0, "domain_name": ""})
                domain_name = nd.get("domain_name") or od.get("domain_name", domain_code)

                demand_before = od.get("demand", 0)
                demand_after = nd.get("demand", 0)
                if demand_before == 0 and demand_after > 0:
                    growth_pct = 100.0
                elif demand_before > 0:
                    growth_pct = round((demand_after - demand_before) / demand_before * 100, 1)
                else:
                    growth_pct = 0.0

                domain_trends.append({
                    "domain_code": domain_code,
                    "domain_name": domain_name,
                    "demand_before": demand_before,
                    "demand_after": demand_after,
                    "growth_pct": growth_pct,
                    "skill_count_before": od.get("skill_count", 0),
                    "skill_count_after": nd.get("skill_count", 0),
                })
            domain_trends.sort(key=lambda x: -abs(x["growth_pct"]))

        # --- 5. AI Insights ---
        insights = _generate_insights(skill_trends, job_trends, status_distribution)

        return {
            "job_trends": job_trends,
            "skill_trends": skill_trends[:50],
            "skill_trends_detail": skill_trends_detail[:50],
            "status_distribution": status_distribution,
            "domain_trends": domain_trends,
            "insights": insights,
            "warnings": warnings,
        }

    except Exception as exc:
        logger.error(f"Reports overview error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


def _generate_insights(skill_trends: list, job_trends: list,
                       status_distribution: list) -> list:
    """Generate actionable insights from trend data.

    Uses configurable thresholds to avoid trivial or misleading results.
    """
    insights = []

    # Insight 1: Fastest growing skills
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

    # Insight 2: Newly appearing skills
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

    # Insight 3: Declining skills
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
