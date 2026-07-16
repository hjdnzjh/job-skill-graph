"""Collector API endpoints — trigger, status, logs, source stats.

Full pipeline: collection → ETL (clean/normalize/dedup/score) → MySQL ingest.
"""

import logging
import threading
import uuid
from datetime import datetime
from typing import Optional

import pymysql
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config.schema import UnifiedJobSchema, DataSourceType, DataFormat
from web._settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/collector", tags=["collector"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TriggerRequest(BaseModel):
    platform: str           # e.g. "tencent", "liepin", "boss_zhipin"
    keyword: str            # e.g. "Java", "Python开发"
    city: str = ""          # e.g. "深圳", "北京"
    max_pages: int = 3


class TriggerResponse(BaseModel):
    run_id: int
    status: str             # "started" or "failed"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_conn():
    """Get a pymysql connection from settings."""
    settings = get_settings()
    return pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        charset="utf8mb4",
    )


def _ensure_table():
    """Create collector_runs table if it does not exist, add missing columns."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS collector_runs (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    platform VARCHAR(32) NOT NULL,
                    keyword VARCHAR(64) NOT NULL,
                    city VARCHAR(32) NOT NULL,
                    started_at DATETIME NOT NULL,
                    finished_at DATETIME,
                    status ENUM('running','success','failed') NOT NULL DEFAULT 'running',
                    records_collected INT DEFAULT 0,
                    pages_crawled INT DEFAULT 0,
                    duration_seconds FLOAT DEFAULT 0,
                    ingested_count INT DEFAULT 0,
                    error_message TEXT NULL,
                    INDEX idx_platform (platform),
                    INDEX idx_status (status),
                    INDEX idx_started (started_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            # Migration: add ingested_count column if table already existed without it
            cur.execute("""
                SELECT COLUMN_NAME FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='collector_runs'
                AND COLUMN_NAME='ingested_count'
            """)
            if not cur.fetchone():
                cur.execute(
                    "ALTER TABLE collector_runs ADD COLUMN ingested_count INT DEFAULT 0"
                )
            conn.commit()
    finally:
        conn.close()


# Ensure table exists on module import
try:
    _ensure_table()
except Exception as e:
    logger.warning(f"collector_runs table init failed (DB may not be ready): {e}")


# ---------------------------------------------------------------------------
# Collector dispatch
# ---------------------------------------------------------------------------

_COLLECTOR_MAP = {}  # lazy-imported


def _get_collector(platform: str):
    """Lazy-import a collector class instance by platform name."""
    if platform not in _COLLECTOR_MAP:
        if platform == "tencent":
            from collector.tencent import TencentCollector
            _COLLECTOR_MAP[platform] = TencentCollector()
        elif platform == "liepin":
            from collector.liepin import LiepinCollector
            _COLLECTOR_MAP[platform] = LiepinCollector()
        elif platform == "boss_zhipin":
            from collector.boss_zhipin import BossZhipinCollector
            _COLLECTOR_MAP[platform] = BossZhipinCollector()
        elif platform == "zhilian":
            from collector.zhilian import ZhilianCollector
            _COLLECTOR_MAP[platform] = ZhilianCollector()
        elif platform == "bytedance":
            from collector.bytedance import BytedanceCollector
            _COLLECTOR_MAP[platform] = BytedanceCollector()
        elif platform == "alibaba":
            from collector.alibaba import AlibabaCollector
            _COLLECTOR_MAP[platform] = AlibabaCollector()
        elif platform == "huawei":
            from collector.huawei import HuaweiCollector
            _COLLECTOR_MAP[platform] = HuaweiCollector()
        else:
            raise ValueError(f"Unknown platform: {platform}")
    return _COLLECTOR_MAP[platform]


# ---------------------------------------------------------------------------
# Platform → source type mapping
# ---------------------------------------------------------------------------

_PLATFORM_SOURCE_TYPE = {
    "tencent": DataSourceType.ENTERPRISE,
    "liepin": DataSourceType.RECRUITMENT,
    "boss_zhipin": DataSourceType.RECRUITMENT,
    "zhilian": DataSourceType.RECRUITMENT,
    "bytedance": DataSourceType.ENTERPRISE,
    "alibaba": DataSourceType.ENTERPRISE,
    "huawei": DataSourceType.ENTERPRISE,
}


def _dict_to_unified_schema(raw: dict, platform: str) -> UnifiedJobSchema:
    """Convert a collector-normalized dict into a UnifiedJobSchema for ETL.

    Collector dict fields (from BaseCollector.normalize):
        source_platform, source_job_id, source_url,
        title, company, city, salary_min, salary_max,
        description, education, experience, industry, skills[]
    """
    skills = raw.get("skills", [])
    if not isinstance(skills, list):
        skills = []

    return UnifiedJobSchema(
        record_id=str(uuid.uuid4()),
        source_id=str(raw.get("source_job_id", "")),
        source_type=_PLATFORM_SOURCE_TYPE.get(platform, DataSourceType.RECRUITMENT),
        source_name=platform,
        source_url=raw.get("source_url", ""),
        job_title=raw.get("title", ""),
        job_title_raw=raw.get("title", ""),
        company_name=raw.get("company", ""),
        company_name_raw=raw.get("company", ""),
        industry=raw.get("industry", ""),
        location=raw.get("city", ""),
        location_raw=raw.get("city", ""),
        job_description=raw.get("description", ""),
        salary_min=raw.get("salary_min"),
        salary_max=raw.get("salary_max"),
        experience_required=raw.get("experience", ""),
        education_required=raw.get("education", ""),
        job_type="",
        skills_required=skills,
        skills_preferred=[],
        abilities=[],
        publish_date=None,
        crawl_timestamp=datetime.now(),
        data_format=DataFormat.SEMI_STRUCTURED,
        extra={"source_platform": platform},
    )


# ---------------------------------------------------------------------------
# Background collection + ingest thread
# ---------------------------------------------------------------------------

def _run_collection_and_ingest(run_id: int, platform: str, keyword: str,
                                city: str, max_pages: int):
    """Background thread: collect → ETL pipeline → MySQL ingest.

    Collection failure → run status = 'failed', no ingest attempted.
    Ingest failure → run status stays 'success' (collection succeeded),
                       ingest error logged separately.
    """
    finished_at = None
    status = "failed"
    records_collected = 0
    pages_crawled = 0
    duration = 0.0
    error_message = None
    ingested_count = 0

    # ------------------------------------------------------------------
    # Phase 1: Collection
    # ------------------------------------------------------------------
    try:
        collector = _get_collector(platform)
        result = collector.collect(keyword, city, max_pages=max_pages)
        status = "success"
        records_collected = len(result.records)
        pages_crawled = result.pages_crawled
        duration = result.duration_seconds
        if result.errors:
            error_message = "; ".join(str(e) for e in result.errors[:5])
            if len(result.errors) > 5:
                error_message += f" ... and {len(result.errors) - 5} more"
        logger.info(
            f"[Collector] run_id={run_id} {platform}/{keyword}/{city}: "
            f"{records_collected} records, {pages_crawled} pages, {duration:.1f}s"
        )
    except Exception as e:
        error_message = str(e)[:1000]
        logger.error(f"[Collector] run_id={run_id} failed: {e}")

    finished_at = datetime.now()

    # Update DB after collection (Phase 1 complete)
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE collector_runs
                   SET status=%s, finished_at=%s, records_collected=%s,
                       pages_crawled=%s, duration_seconds=%s, error_message=%s
                   WHERE id=%s""",
                (status, finished_at, records_collected, pages_crawled,
                 duration, error_message, run_id),
            )
            conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[Collector] Failed to update run {run_id}: {e}")

    # ------------------------------------------------------------------
    # Phase 2: ETL + MySQL ingest (only if collection succeeded)
    # ------------------------------------------------------------------
    if status != "success" or records_collected == 0:
        return

    try:
        # 2a. Convert collector dicts → UnifiedJobSchema
        unified_records = []
        for raw in result.records:
            try:
                unified_records.append(_dict_to_unified_schema(raw, platform))
            except Exception as e:
                logger.warning(f"[Ingest] run_id={run_id} schema conversion failed: {e}")

        if not unified_records:
            logger.warning(f"[Ingest] run_id={run_id}: no records after conversion")
            return

        # 2b. ETL Pipeline: Clean → Normalize → Deduplicate → Score
        from etl.cleaner import DataCleaner
        from etl.normalizer import Normalizer
        from etl.deduplicator import Deduplicator
        from etl.quality import QualityScorer

        settings = get_settings()

        cleaner = DataCleaner()
        normalizer = Normalizer()
        deduplicator = Deduplicator(
            similarity_threshold=settings.dedup_similarity_threshold,
        )
        scorer = QualityScorer(min_score=settings.quality_min_score)

        # Clean: whitespace, HTML, encoding, drop empty-title records
        cleaned = cleaner.clean(unified_records)
        etl_stats = {"after_clean": len(cleaned)}

        # Normalize: canonical job titles, locations, salaries, skills
        normalized = normalizer.normalize(cleaned)

        # Deduplicate: exact-key + MinHash LSH
        deduped = deduplicator.deduplicate(normalized)
        etl_stats["after_dedup"] = len(deduped)

        # Score: completeness / freshness / consistency, filter low quality
        scored = scorer.score_batch(deduped)
        etl_stats["after_quality"] = len(scored)

        if not scored:
            logger.info(f"[Ingest] run_id={run_id}: all records filtered out by quality")
            ingested_count = 0
        else:
            # 2c. MySQL Insert
            from storage.mysql_client import MySQLClient
            mysql = MySQLClient(settings)
            mysql.init_db()
            ingested_count = mysql.insert_batch(scored, batch_size=settings.batch_size)

        logger.info(
            f"[Ingest] run_id={run_id}: collected={records_collected} → "
            f"clean={etl_stats['after_clean']} → dedup={etl_stats['after_dedup']} → "
            f"quality={etl_stats['after_quality']} → mysql={ingested_count}"
        )

        quality_summary = QualityScorer.summary(scored) if scored else {}
        if quality_summary.get("total", 0) > 0:
            logger.info(
                f"[Ingest] run_id={run_id}: avg_quality={quality_summary.get('avg_quality', 0):.3f}, "
                f"grades={quality_summary.get('grade_distribution', {})}"
            )

    except Exception as e:
        logger.error(
            f"[Ingest] run_id={run_id} ingest failed (collection OK): {e}",
            exc_info=True,
        )
        error_message = (error_message or "") + f" [INGEST_FAILED: {str(e)[:500]}]"

    # ------------------------------------------------------------------
    # Update run with ingest count (always attempted, even on partial failure)
    # ------------------------------------------------------------------
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE collector_runs SET ingested_count=%s, error_message=%s WHERE id=%s",
                (ingested_count, error_message, run_id),
            )
            conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[Ingest] Failed to update ingest metadata for run {run_id}: {e}")


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.post("/trigger", response_model=TriggerResponse)
async def trigger_collection(req: TriggerRequest):
    """Manually trigger a collection run (async, non-blocking).

    Request body:
        {"platform":"tencent", "keyword":"Java", "city":"深圳", "max_pages":3}

    Returns:
        {"run_id": 123, "status": "started"}
    """
    # Validate platform
    valid_platforms = [
        "tencent", "liepin", "boss_zhipin", "zhilian",
        "bytedance", "alibaba", "huawei",
    ]
    if req.platform not in valid_platforms:
        return JSONResponse(
            {"error": f"Unknown platform: {req.platform}. Valid: {valid_platforms}"},
            status_code=400,
        )

    started_at = datetime.now()

    # Insert run record with status 'running'
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO collector_runs
                   (platform, keyword, city, started_at, status)
                   VALUES (%s, %s, %s, %s, 'running')""",
                (req.platform, req.keyword, req.city, started_at),
            )
            conn.commit()
            run_id = cur.lastrowid
        conn.close()
    except Exception as e:
        logger.error(f"Failed to insert run record: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

    # Start collection + ingest in background thread
    t = threading.Thread(
        target=_run_collection_and_ingest,
        args=(run_id, req.platform, req.keyword, req.city, req.max_pages),
        daemon=True,
    )
    t.start()

    return TriggerResponse(run_id=run_id, status="started")


@router.get("/status")
async def collector_status():
    """Get latest collection status for each platform.

    Returns one row per platform with the most recent run.
    """
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT platform, keyword, city, status,
                       started_at, finished_at, records_collected,
                       pages_crawled, duration_seconds, ingested_count, error_message
                FROM collector_runs r1
                WHERE id = (
                    SELECT id FROM collector_runs r2
                    WHERE r2.platform = r1.platform
                    ORDER BY started_at DESC LIMIT 1
                )
                ORDER BY platform
            """)
            rows = cur.fetchall()
        conn.close()

        results = []
        for row in rows:
            results.append({
                "platform": row[0],
                "keyword": row[1],
                "city": row[2],
                "status": row[3],
                "started_at": row[4].isoformat() if row[4] else None,
                "finished_at": row[5].isoformat() if row[5] else None,
                "records_collected": row[6] or 0,
                "pages_crawled": row[7] or 0,
                "duration_seconds": row[8] or 0,
                "ingested_count": row[9] or 0,
                "error_message": row[10],
            })
        return JSONResponse(results)
    except Exception as e:
        logger.error(f"collector/status error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/logs")
async def collector_logs(
    platform: Optional[str] = Query(None, description="Filter by platform"),
    limit: int = Query(20, ge=1, le=200, description="Max rows returned"),
    offset: int = Query(0, ge=0, description="Row offset for pagination"),
):
    """Get paginated collection run logs.

    Query params:
        platform  - filter by platform (optional)
        limit     - max rows (default 20, max 200)
        offset    - pagination offset (default 0)
    """
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            if platform:
                cur.execute(
                    """SELECT id, platform, keyword, city, status,
                              started_at, finished_at, records_collected,
                              pages_crawled, duration_seconds, ingested_count, error_message
                       FROM collector_runs
                       WHERE platform = %s
                       ORDER BY started_at DESC
                       LIMIT %s OFFSET %s""",
                    (platform, limit, offset),
                )
            else:
                cur.execute(
                    """SELECT id, platform, keyword, city, status,
                              started_at, finished_at, records_collected,
                              pages_crawled, duration_seconds, ingested_count, error_message
                       FROM collector_runs
                       ORDER BY started_at DESC
                       LIMIT %s OFFSET %s""",
                    (limit, offset),
                )
            rows = cur.fetchall()

            # Get total count
            if platform:
                cur.execute(
                    "SELECT COUNT(*) FROM collector_runs WHERE platform=%s",
                    (platform,),
                )
            else:
                cur.execute("SELECT COUNT(*) FROM collector_runs")
            total = cur.fetchone()[0]
        conn.close()

        logs = []
        for row in rows:
            logs.append({
                "id": row[0],
                "platform": row[1],
                "keyword": row[2],
                "city": row[3],
                "status": row[4],
                "started_at": row[5].isoformat() if row[5] else None,
                "finished_at": row[6].isoformat() if row[6] else None,
                "records_collected": row[7] or 0,
                "pages_crawled": row[8] or 0,
                "duration_seconds": row[9] or 0,
                "ingested_count": row[10] or 0,
                "error_message": row[11],
            })

        return JSONResponse({"total": total, "limit": limit, "offset": offset, "logs": logs})
    except Exception as e:
        logger.error(f"collector/logs error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/sources")
async def collector_sources():
    """Get per-platform source statistics: record count, last update, quality.

    Reads from both collector_runs (collection metadata) and job_records
    (stored data via source_platform in extra JSON field).
    """
    try:
        conn = _get_conn()
        with conn.cursor() as cur:
            # Get run-level stats per platform
            cur.execute("""
                SELECT
                    platform,
                    COUNT(*) AS total_runs,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_runs,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_runs,
                    SUM(records_collected) AS total_records,
                    MAX(finished_at) AS last_update
                FROM collector_runs
                GROUP BY platform
                ORDER BY platform
            """)
            rows = cur.fetchall()
        conn.close()

        sources = []
        for row in rows:
            sources.append({
                "platform": row[0],
                "total_runs": row[1] or 0,
                "success_runs": row[2] or 0,
                "failed_runs": row[3] or 0,
                "total_records_collected": row[4] or 0,
                "last_update": row[5].isoformat() if row[5] else None,
            })

        return JSONResponse(sources)
    except Exception as e:
        logger.error(f"collector/sources error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
