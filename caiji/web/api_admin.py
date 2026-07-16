"""Admin endpoints: health check, API call statistics, alerts, cleanup."""

import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pymysql
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
from pydantic import BaseModel

from web._settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

_START_TIME = time.time()

# ── data models ────────────────────────────────────────────────────

class AlertAckResponse(BaseModel):
    id: int
    acknowledged: bool
    acknowledged_at: Optional[str] = None
    message: str


class CleanupResult(BaseModel):
    target: str
    results: dict


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@router.get("/health")
async def health_check():
    """Return service health status with MySQL + Neo4j connectivity."""
    settings = get_settings()
    overall = "ok"
    health = {
        "status": overall,
        "mysql": _check_mysql(settings),
        "neo4j": _check_neo4j(settings),
        "uptime_seconds": round(time.time() - _START_TIME, 1),
    }
    if not health["mysql"]["connected"] or not health["neo4j"]["connected"]:
        health["status"] = "degraded"
    return health


def _check_mysql(settings) -> dict:
    try:
        t0 = time.time()
        conn = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database,
            charset="utf8mb4",
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            conn.close()
        latency_ms = round((time.time() - t0) * 1000, 2)
        return {"connected": True, "latency_ms": latency_ms}
    except Exception as exc:
        logger.warning(f"MySQL health check failed: {exc}")
        return {"connected": False, "error": str(exc)}


def _check_neo4j(settings) -> dict:
    try:
        t0 = time.time()
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        try:
            driver.verify_connectivity()
        finally:
            driver.close()
        latency_ms = round((time.time() - t0) * 1000, 2)
        return {"connected": True, "latency_ms": latency_ms}
    except (ServiceUnavailable, Exception) as exc:
        logger.warning(f"Neo4j health check failed: {exc}")
        return {"connected": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Helper: query api_request_logs
# ---------------------------------------------------------------------------
def _percentile(sorted_values: list[float], pct: float) -> float:
    """Return the pct-th percentile from a sorted list of floats."""
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct
    f = int(k)
    c = k - f
    if f + 1 < len(sorted_values):
        return round(sorted_values[f] + c * (sorted_values[f + 1] - sorted_values[f]), 2)
    return round(sorted_values[f], 2)


def _query_logs(settings, sql: str, params=None) -> list[dict]:
    """Execute a SELECT against api_request_logs, returning list of dicts."""
    conn = pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# API call statistics
# ---------------------------------------------------------------------------
@router.get("/stats")
async def api_stats():
    """Return API call statistics for the last 24 hours."""
    settings = get_settings()
    try:
        total = _query_logs(
            settings,
            "SELECT count(*) AS cnt FROM api_request_logs "
            "WHERE timestamp >= NOW() - INTERVAL 1 DAY",
        )
        total_requests = total[0]["cnt"] if total else 0

        errors = _query_logs(
            settings,
            "SELECT count(*) AS cnt FROM api_request_logs "
            "WHERE timestamp >= NOW() - INTERVAL 1 DAY AND status_code >= 400",
        )
        error_count = errors[0]["cnt"] if errors else 0
        error_rate = round(error_count / total_requests, 4) if total_requests else 0

        # Percentiles: fetch all durations from last 24h and compute in Python.
        # This is robust across MySQL versions and avoids unsupported
        # PERCENTILE_CONT / LIMIT-subquery constructs.
        p50, p99 = 0.0, 0.0
        if total_requests > 0:
            dur_rows = _query_logs(
                settings,
                "SELECT duration_ms FROM api_request_logs "
                "WHERE timestamp >= NOW() - INTERVAL 1 DAY "
                "ORDER BY duration_ms",
            )
            if dur_rows:
                durations = [r["duration_ms"] for r in dur_rows]
                p50 = _percentile(durations, 0.50)
                p99 = _percentile(durations, 0.99)

        # By hour
        by_hour = _query_logs(
            settings,
            "SELECT DATE_FORMAT(timestamp, '%Y-%m-%dT%H:00') AS hour, "
            "       count(*) AS cnt "
            "FROM api_request_logs "
            "WHERE timestamp >= NOW() - INTERVAL 1 DAY "
            "GROUP BY hour ORDER BY hour",
        )
        by_hour = [{"hour": r["hour"], "count": r["cnt"]} for r in by_hour]

        # Top endpoints
        top = _query_logs(
            settings,
            "SELECT path, count(*) AS cnt "
            "FROM api_request_logs "
            "WHERE timestamp >= NOW() - INTERVAL 1 DAY "
            "GROUP BY path ORDER BY cnt DESC LIMIT 10",
        )
        top_endpoints = [{"path": r["path"], "count": r["cnt"]} for r in top]

        return {
            "period": "last_24h",
            "total_requests": total_requests,
            "error_rate": error_rate,
            "p50_ms": p50,
            "p99_ms": p99,
            "by_hour": by_hour,
            "top_endpoints": top_endpoints,
        }
    except Exception as exc:
        logger.exception(f"Stats API error: {exc}")
        return JSONResponse(
            {"error": f"统计查询失败: {exc}", "period": "last_24h",
             "total_requests": 0, "error_rate": 0, "p50_ms": 0, "p99_ms": 0,
             "by_hour": [], "top_endpoints": []},
            status_code=500,
        )


@router.get("/stats/endpoints")
async def api_endpoint_stats():
    """Return aggregated counts per endpoint path."""
    settings = get_settings()
    try:
        rows = _query_logs(
            settings,
            "SELECT path, count(*) AS total, "
            "       AVG(duration_ms) AS avg_ms, "
            "       SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS errors "
            "FROM api_request_logs "
            "GROUP BY path ORDER BY total DESC",
        )
        return {
            "endpoints": [
                {
                    "path": r["path"],
                    "total_requests": r["total"],
                    "avg_duration_ms": round(r["avg_ms"] or 0, 2),
                    "errors": r["errors"],
                }
                for r in rows
            ]
        }
    except Exception as exc:
        logger.exception(f"Endpoint stats API error: {exc}")
        return JSONResponse(
            {"error": f"端点统计查询失败: {exc}", "endpoints": []},
            status_code=500,
        )


# ---------------------------------------------------------------------------
# Alerting
# ---------------------------------------------------------------------------

def _get_mysql_conn(settings):
    """Return a new pymysql connection (caller must close)."""
    return pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        charset="utf8mb4",
    )


def _ensure_alerts_table(settings):
    """CREATE TABLE IF NOT EXISTS for alerts."""
    conn = _get_mysql_conn(settings)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    severity ENUM('info','warning','error','critical') NOT NULL DEFAULT 'warning',
                    source VARCHAR(64) NOT NULL,
                    message TEXT NOT NULL,
                    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
                    acknowledged_at DATETIME NULL,
                    INDEX idx_created (created_at),
                    INDEX idx_acknowledged (acknowledged)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            conn.commit()
        logger.info("Alerts table ready.")
    finally:
        conn.close()


def raise_alert(source: str, message: str, severity: str = "warning"):
    """Write an alert row to the ``alerts`` table.

    Fire-and-forget — callers do not wait for a result.
    """
    try:
        settings = get_settings()
        conn = _get_mysql_conn(settings)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO alerts (severity, source, message) "
                    "VALUES (%s, %s, %s)",
                    (severity, source, message),
                )
                conn.commit()
            logger.info("Alert raised [%s] %s: %s", severity, source, message[:120])
        finally:
            conn.close()
    except Exception as exc:
        logger.error("Failed to raise alert: %s", exc)


# Ensure alerts table exists on module load
try:
    _ensure_alerts_table(get_settings())
except Exception:
    pass  # MySQL may not be available at import time


@router.get("/alerts")
async def list_alerts(
    severity: Optional[str] = Query(None, description="Filter: info|warning|error|critical"),
    acknowledged: Optional[bool] = Query(None, description="Filter acknowledged status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Paginated alert list with optional severity and acknowledged filters."""
    settings = get_settings()
    try:
        conn = _get_mysql_conn(settings)
        try:
            conditions = []
            params = []
            if severity:
                conditions.append("severity = %s")
                params.append(severity)
            if acknowledged is not None:
                conditions.append("acknowledged = %s")
                params.append(acknowledged)

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            with conn.cursor() as cur:
                # Count
                cur.execute(f"SELECT COUNT(*) FROM alerts {where_clause}", params)
                total = cur.fetchone()[0]

                # Page
                offset = (page - 1) * page_size
                cur.execute(
                    f"SELECT id, created_at, severity, source, message, "
                    f"acknowledged, acknowledged_at "
                    f"FROM alerts {where_clause} "
                    f"ORDER BY created_at DESC "
                    f"LIMIT %s OFFSET %s",
                    params + [page_size, offset],
                )
                rows = cur.fetchall()

            items = []
            for r in rows:
                items.append({
                    "id": r[0],
                    "created_at": r[1].isoformat() if r[1] else None,
                    "severity": r[2],
                    "source": r[3],
                    "message": r[4],
                    "acknowledged": bool(r[5]),
                    "acknowledged_at": r[6].isoformat() if r[6] else None,
                })

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": items,
            }
        finally:
            conn.close()
    except Exception as exc:
        logger.exception("list_alerts failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int):
    """Mark a single alert as acknowledged."""
    settings = get_settings()
    try:
        conn = _get_mysql_conn(settings)
        try:
            now = datetime.now()
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE alerts SET acknowledged = TRUE, acknowledged_at = %s "
                    "WHERE id = %s",
                    (now, alert_id),
                )
                conn.commit()
                if cur.rowcount == 0:
                    return JSONResponse(
                        {"error": f"Alert {alert_id} not found"}, status_code=404
                    )

            return AlertAckResponse(
                id=alert_id,
                acknowledged=True,
                acknowledged_at=now.isoformat(),
                message=f"Alert {alert_id} acknowledged.",
            ).model_dump()
        finally:
            conn.close()
    except Exception as exc:
        logger.exception("acknowledge_alert failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@router.post("/cleanup")
async def trigger_cleanup(
    target: str = Query("all", description="snapshots | processed | logs | all"),
):
    """Manually trigger data cleanup tasks."""
    from config.settings import Settings
    cfg = Settings()
    results = {}

    root = _get_project_root()
    snap_dir = root / "data" / "snapshots"
    processed_dir = root / "data" / "processed"

    try:
        # ── snapshots ──
        if target in ("snapshots", "all"):
            snap_deleted = 0
            if snap_dir.is_dir():
                files = sorted(
                    [f for f in snap_dir.glob("*.json") if f.name != "snapshot_index.json"],
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                for fp in files[cfg.cleanup_snapshot_keep:]:
                    try:
                        fp.unlink()
                        snap_deleted += 1
                    except OSError as exc:
                        logger.warning("Failed to delete snapshot %s: %s", fp.name, exc)
            results["snapshots"] = f"deleted {snap_deleted}, kept {cfg.cleanup_snapshot_keep}"

        # ── processed files ──
        if target in ("processed", "all"):
            proc_deleted = 0
            if processed_dir.is_dir():
                cutoff = time.time() - cfg.cleanup_processed_days * 86400
                for fp in processed_dir.glob("*_recruitment_raw.jsonl"):
                    try:
                        if fp.stat().st_mtime < cutoff:
                            fp.unlink()
                            proc_deleted += 1
                    except OSError as exc:
                        logger.warning("Failed to delete processed file %s: %s", fp.name, exc)
            results["processed"] = f"deleted {proc_deleted} files older than {cfg.cleanup_processed_days}d"

        # ── request logs ──
        if target in ("logs", "all"):
            try:
                conn = _get_mysql_conn(cfg)
                try:
                    cutoff_date = datetime.now() - timedelta(days=cfg.cleanup_request_logs_days)
                    with conn.cursor() as cur:
                        cur.execute(
                            "DELETE FROM api_request_logs WHERE timestamp < %s",
                            (cutoff_date,),
                        )
                        conn.commit()
                        log_deleted = cur.rowcount
                    results["logs"] = f"deleted {log_deleted} rows older than {cfg.cleanup_request_logs_days}d"
                finally:
                    conn.close()
            except Exception as exc:
                results["logs"] = f"cleanup failed: {exc}"

        return CleanupResult(target=target, results=results).model_dump()

    except Exception as exc:
        logger.exception("trigger_cleanup failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)
