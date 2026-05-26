"""Evolution snapshot timeline and comparison API."""

import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from web.server import get_settings

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
