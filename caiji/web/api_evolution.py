"""Evolution snapshot timeline and comparison API."""

import logging
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
