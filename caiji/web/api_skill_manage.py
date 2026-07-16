"""Skill change management API for admin dashboard.

Provides endpoints for viewing, analyzing, and confirming skill
requirement changes across job titles.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from web._settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/skills", tags=["skill-manage"])


@router.get("/changes")
async def list_changes(
    limit: int = Query(default=50, ge=1, le=500, description="Max records returned"),
    offset: int = Query(default=0, ge=0, description="Record offset for pagination"),
):
    """Return paginated skill change records across all jobs."""
    try:
        from kg.job_updater import JobUpdater
        updater = JobUpdater(get_settings())
        records = updater.list_all_changes(limit=limit, offset=offset)
        total = updater.count_all_changes()
        updater.close()
        return {"changes": records, "total": total, "offset": offset, "limit": limit}
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
    """Confirm and archive skill changes for a job title.

    Stores confirmation metadata on the JobTitle node in Neo4j.
    """
    try:
        from kg.job_updater import JobUpdater
        from datetime import datetime
        updater = JobUpdater(get_settings())
        result = updater.analyze(title)

        confirmed_at = datetime.now().isoformat()

        # Store confirmation on JobTitle node (or ChangeConfirmation if no match)
        changes_summary = result.get("summary", "已确认")
        new_count = len(result.get("new_skills", []))
        removed_count = len(result.get("removed_skills", []))

        updater.neo4j.run_query(
            "MATCH (t:JobTitle {name: $title}) "
            "SET t.confirmed_at = $confirmed_at, "
            "    t.confirmed_new_skills = $new_count, "
            "    t.confirmed_removed_skills = $removed_count",
            {
                "title": title,
                "confirmed_at": confirmed_at,
                "new_count": new_count,
                "removed_count": removed_count,
            },
        )

        # Also create a ChangeConfirmation node for audit trail
        updater.neo4j.run_query(
            "MERGE (cc:ChangeConfirmation {title: $title, confirmed_at: $confirmed_at}) "
            "SET cc.summary = $summary, "
            "    cc.new_count = $new_count, "
            "    cc.removed_count = $removed_count",
            {
                "title": title,
                "confirmed_at": confirmed_at,
                "summary": changes_summary,
                "new_count": new_count,
                "removed_count": removed_count,
            },
        )

        updater.close()

        return {
            "status": "confirmed",
            "title": title,
            "summary": changes_summary,
            "confirmed_at": confirmed_at,
        }
    except Exception as exc:
        logger.error(f"Skill change confirm error: {exc}")
        return JSONResponse({"error": str(exc)}, status_code=500)
