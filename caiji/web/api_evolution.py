"""Evolution snapshot timeline and comparison API."""

import logging
import os
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from web._settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/evolution", tags=["evolution"])


@router.get("/timeline")
async def get_timeline():
    """Return summary of all evolution snapshots."""
    try:
        from kg.evolution import EvolutionTracker
        tracker = EvolutionTracker(get_settings())
        snapshot_files = tracker.list_snapshots()
        timeline = []
        for f in sorted(snapshot_files):
            snap = tracker.load_snapshot(f)
            if snap:
                timeline.append({
                    "file": f,
                    "timestamp": snap.get("timestamp", ""),
                    "record_count": snap.get("record_count", 0),
                    "total_nodes": snap.get("graph", {}).get("total_nodes", 0),
                    "total_edges": snap.get("graph", {}).get("total_edges", 0),
                    "top_skill": snap.get("top_skills", [{}])[0] if snap.get("top_skills") else None,
                })
        return {"timeline": timeline}
    except Exception as exc:
        logger.error(f"Evolution timeline API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/compare")
async def compare_snapshots(
    a: int = Query(default=0, description="First snapshot index"),
    b: int = Query(default=-1, description="Second snapshot index (-1 means latest)"),
):
    """Compare two snapshots and return structured diff."""
    try:
        from kg.evolution import EvolutionTracker
        tracker = EvolutionTracker(get_settings())
        files = tracker.list_snapshots()
        if not files:
            return JSONResponse(
                {"error": "暂无演化快照，请先运行 --snapshot 生成快照"},
                status_code=404,
            )

        idx_a = a
        idx_b = b if b >= 0 else len(files) - 1
        if idx_a >= len(files) or idx_b >= len(files):
            return JSONResponse(
                {"error": f"快照索引超出范围 (共 {len(files)} 个快照)"},
                status_code=400,
            )

        diff = tracker.compare(files[idx_a], files[idx_b])
        return diff
    except Exception as exc:
        logger.error(f"Evolution compare API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/category-trends")
async def get_category_trends():
    """Load oldest and newest snapshots and compute domain-level demand trends."""
    try:
        from kg.evolution import EvolutionTracker
        tracker = EvolutionTracker(get_settings())
        files = tracker.list_snapshots()
        if len(files) < 2:
            return JSONResponse(
                {"error": "需要至少 2 个快照才能计算分类趋势"},
                status_code=400,
            )

        oldest = tracker.load_snapshot(files[0])
        newest = tracker.load_snapshot(files[-1])

        old_domains = {
            d["domain"]: d
            for d in oldest.get("skills_by_domain", [])
        } if oldest.get("skills_by_domain") else {}
        new_domains = {
            d["domain"]: d
            for d in newest.get("skills_by_domain", [])
        } if newest.get("skills_by_domain") else {}

        category_trends = []
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

            skill_before = od.get("skill_count", 0)
            skill_after = nd.get("skill_count", 0)

            category_trends.append({
                "domain_code": domain_code,
                "domain_name": domain_name,
                "demand_before": demand_before,
                "demand_after": demand_after,
                "growth_pct": growth_pct,
                "skill_count_before": skill_before,
                "skill_count_after": skill_after,
            })

        category_trends.sort(key=lambda x: -abs(x["growth_pct"]))
        return {"category_trends": category_trends}
    except Exception as exc:
        logger.error(f"Category trends API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/summary")
async def get_evolution_summary():
    """Return a comprehensive evolution dashboard summary.

    Data sourced entirely from snapshot JSON files — no live DB queries.
    """
    try:
        from kg.evolution import EvolutionTracker
        tracker = EvolutionTracker(get_settings())
        files = tracker.list_snapshots()

        if not files:
            return JSONResponse(
                {"error": "暂无演化快照，请先运行 --snapshot 生成快照"},
                status_code=404,
            )

        first = tracker.load_snapshot(files[0])
        latest = tracker.load_snapshot(files[-1])

        # --- snapshot_span ---
        snapshot_span = _format_span(
            first.get("timestamp", ""), latest.get("timestamp", "")
        )

        # --- total_growth ---
        total_growth = _compute_total_growth(first, latest)

        # --- cross_platform (from latest snapshot's platform_distribution) ---
        cross_platform = _build_cross_platform(latest)

        # --- cross_domain (from snapshot skills_by_domain) ---
        cross_domain = _build_cross_domain(latest)

        # --- top_new_skills (largest demand growth from first to latest) ---
        top_new_skills = _compute_top_new_skills(first, latest)

        # --- total_sources ---
        total_sources = (
            latest.get("platform_distribution", {})
            .get("total_sources", 0)
        )

        # --- data_quality ---
        real_count = len(files)
        simulated_count = sum(
            1 for f in files if "simulated" in os.path.basename(f).lower()
        )

        return {
            "snapshot_span": snapshot_span,
            "total_growth": total_growth,
            "cross_platform": cross_platform,
            "cross_domain": cross_domain,
            "top_new_skills": top_new_skills,
            "total_sources": total_sources,
            "data_quality": {
                "real_snapshots": real_count - simulated_count,
                "simulated_snapshots": simulated_count,
            },
        }
    except Exception as exc:
        logger.error(f"Evolution summary API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/industry-trends")
async def get_industry_trends():
    """Return per-industry trends: jobs, avg salary, top skills, MoM changes.

    Queries Neo4j for current state, and uses snapshots for comparison.
    """
    try:
        from kg.evolution import EvolutionTracker
        from kg.neo4j_client import Neo4jClient
        tracker = EvolutionTracker(get_settings())
        neo4j = Neo4jClient(get_settings())

        # --- Current industry state from Neo4j ---
        industry_rows = neo4j.run_query(
            "MATCH (j:Job)-[:BELONGS_TO]->(ind:Industry) "
            "RETURN ind.name AS industry, count(j) AS jobs, "
            "avg(j.salary_min) AS avg_salary_min, "
            "avg(j.salary_max) AS avg_salary_max "
            "ORDER BY jobs DESC"
        )
        total_jobs = sum(r["jobs"] for r in industry_rows) if industry_rows else 0

        # --- Top skills per industry ---
        industry_skills = {}
        if industry_rows:
            ind_names = [r["industry"] for r in industry_rows]
            # Batch query top 5 skills per industry
            skill_rows = neo4j.run_query(
                "MATCH (j:Job)-[:BELONGS_TO]->(ind:Industry) "
                "MATCH (j)-[:REQUIRES]->(s:Skill) "
                "RETURN ind.name AS industry, s.name AS skill, "
                "s.category AS category, count(*) AS demand "
                "ORDER BY industry, demand DESC"
            )
            for r in skill_rows:
                ind = r["industry"]
                if ind not in industry_skills:
                    industry_skills[ind] = []
                industry_skills[ind].append({
                    "skill": r["skill"],
                    "category": r.get("category", ""),
                    "demand": r["demand"],
                })
            # Keep only top 5 per industry
            for ind in industry_skills:
                industry_skills[ind] = industry_skills[ind][:5]

        neo4j.close()

        # --- Build current snapshot ---
        current = []
        for r in industry_rows:
            entry = {
                "industry": r["industry"],
                "jobs": r["jobs"],
                "share_pct": round(r["jobs"] / total_jobs * 100, 1) if total_jobs > 0 else 0.0,
                "avg_salary_min": round(r.get("avg_salary_min", 0) or 0, 2),
                "avg_salary_max": round(r.get("avg_salary_max", 0) or 0, 2),
                "top_skills": industry_skills.get(r["industry"], []),
            }
            current.append(entry)

        # --- MoM comparison if 2+ snapshots ---
        snapshots = tracker.list_snapshots()
        mom_changes = None
        if len(snapshots) >= 2:
            old_snap = tracker.load_snapshot(snapshots[0])
            old_industries = {
                r["industry"]: r
                for r in old_snap.get("industry_distribution", [])
            }

            for entry in current:
                ind_name = entry["industry"]
                old_jobs = old_industries.get(ind_name, {}).get("jobs", 0)
                new_jobs = entry["jobs"]
                if old_jobs > 0:
                    entry["mom_growth_pct"] = round(
                        (new_jobs - old_jobs) / old_jobs * 100, 1
                    )
                elif new_jobs > 0:
                    entry["mom_growth_pct"] = 100.0
                else:
                    entry["mom_growth_pct"] = 0.0
                entry["jobs_before"] = old_jobs

            mom_changes = {
                "baseline_snapshot": old_snap.get("timestamp", ""),
                "current_snapshot": latest_snapshot_timestamp(snapshots),
            }

        return {
            "industries": current,
            "total_industries": len(current),
            "total_jobs": total_jobs,
            "mom_changes": mom_changes,
        }
    except Exception as exc:
        logger.error(f"Industry trends API error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)


# ------------------------------------------------------------------
# Helper functions for /api/evolution/summary and /api/evolution/industry-trends
# ------------------------------------------------------------------

def _format_span(first_ts: str, last_ts: str) -> str:
    """Format a time span like '2026-06-08 → 2026-07-18'."""
    def _short(ts):
        return ts[:10] if ts and len(ts) >= 10 else ts or "?"
    return f"{_short(first_ts)} → {_short(last_ts)}"


def _compute_total_growth(first: dict, latest: dict) -> dict:
    """Compute total growth percentages from first to latest snapshot."""
    f_jobs = first.get("record_count", 0)
    l_jobs = latest.get("record_count", 0)

    f_skills = len(first.get("top_skills", []))
    l_skills = len(latest.get("top_skills", []))

    f_companies = len(first.get("top_companies", []))
    l_companies = len(latest.get("top_companies", []))

    def _pct(old, new):
        if old == 0 and new > 0:
            return 100
        if old > 0:
            return round((new - old) / old * 100, 1)
        return 0

    return {
        "jobs": _pct(f_jobs, l_jobs),
        "skills": _pct(f_skills, l_skills),
        "companies": _pct(f_companies, l_companies),
    }


def _build_cross_platform(latest: dict) -> dict:
    """Build cross-platform distribution from snapshot platform_distribution."""
    pd = latest.get("platform_distribution", {})
    by_platform = pd.get("by_platform", {})
    total = sum(by_platform.values()) if by_platform else 0

    result = {}
    for platform, count in sorted(by_platform.items(), key=lambda x: -x[1]):
        result[platform] = {
            "count": count,
            "share_pct": round(count / total * 100, 1) if total > 0 else 0.0,
        }
    return result


def _build_cross_domain(latest: dict) -> list:
    """Build cross-domain distribution from snapshot skills_by_domain."""
    domains = latest.get("skills_by_domain", [])
    total_demand = sum(d.get("demand", 0) for d in domains) if domains else 0

    result = []
    for d in domains:
        demand = d.get("demand", 0)
        result.append({
            "name": d.get("domain_name", d.get("domain", "")),
            "code": d.get("domain", ""),
            "demand": demand,
            "share_pct": round(demand / total_demand * 100, 1) if total_demand > 0 else 0.0,
            "skill_count": d.get("skill_count", 0),
        })
    return result


def _compute_top_new_skills(first: dict, latest: dict) -> list:
    """Find skills with largest absolute demand growth from first to latest."""
    old_skills = {s["skill"]: s.get("demand", 0) for s in first.get("top_skills", [])}
    new_skills = {s["skill"]: s.get("demand", 0) for s in latest.get("top_skills", [])}

    growth = []
    for skill, new_demand in new_skills.items():
        old_demand = old_skills.get(skill, 0)
        delta = new_demand - old_demand
        if delta > 0:
            growth.append({
                "skill": skill,
                "demand_before": old_demand,
                "demand_after": new_demand,
                "growth": delta,
            })

    growth.sort(key=lambda x: -x["growth"])
    return growth[:10]


def latest_snapshot_timestamp(snapshots: list) -> str:
    """Get the timestamp from the latest snapshot file."""
    try:
        import json
        with open(snapshots[-1], "r", encoding="utf-8") as f:
            return json.load(f).get("timestamp", "")
    except Exception:
        return ""
