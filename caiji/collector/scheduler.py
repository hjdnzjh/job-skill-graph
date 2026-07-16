"""Collector scheduler — periodic data collection via APScheduler."""

import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.base import JobLookupError

logger = logging.getLogger(__name__)


class CollectorScheduler:
    """Manages periodic collection jobs using APScheduler.

    Usage:
        scheduler = CollectorScheduler()
        scheduler.add_job("tencent", "Java", "深圳", interval_hours=12)
        scheduler.add_job("liepin", "Python开发", "北京", interval_hours=24)
        scheduler.start()
        # ... application runs ...
        scheduler.stop()
    """

    def __init__(self):
        self._scheduler = BackgroundScheduler(
            job_defaults={
                "coalesce": True,           # skip missed runs
                "max_instances": 1,         # don't overlap
                "misfire_grace_time": 300,  # 5 min grace for missed runs
            }
        )
        self._collector_cache = {}  # lazy-loaded collector instances

    def _get_collector(self, platform: str):
        """Lazy-load a collector instance by platform name."""
        if platform not in self._collector_cache:
            if platform == "tencent":
                from collector.tencent import TencentCollector
                self._collector_cache[platform] = TencentCollector()
            elif platform == "liepin":
                from collector.liepin import LiepinCollector
                self._collector_cache[platform] = LiepinCollector()
            elif platform == "boss_zhipin":
                from collector.boss_zhipin import BossZhipinCollector
                self._collector_cache[platform] = BossZhipinCollector()
            elif platform == "zhilian":
                from collector.zhilian import ZhilianCollector
                self._collector_cache[platform] = ZhilianCollector()
            elif platform == "bytedance":
                from collector.bytedance import BytedanceCollector
                self._collector_cache[platform] = BytedanceCollector()
            elif platform == "alibaba":
                from collector.alibaba import AlibabaCollector
                self._collector_cache[platform] = AlibabaCollector()
            elif platform == "huawei":
                from collector.huawei import HuaweiCollector
                self._collector_cache[platform] = HuaweiCollector()
            else:
                raise ValueError(f"Unknown platform: {platform}")
        return self._collector_cache[platform]

    def _run_collection_job(self, platform: str, keyword: str, city: str, max_pages: int = 3):
        """Internal: execute a collection run and log to collector_runs table."""
        import pymysql
        from config.settings import Settings

        settings = Settings()
        run_id = None
        started_at = datetime.now()

        # Insert run start
        try:
            conn = pymysql.connect(
                host=settings.mysql_host, port=settings.mysql_port,
                user=settings.mysql_user, password=settings.mysql_password,
                database=settings.mysql_database, charset="utf8mb4",
            )
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO collector_runs
                       (platform, keyword, city, started_at, status)
                       VALUES (%s, %s, %s, %s, 'running')""",
                    (platform, keyword, city, started_at),
                )
                conn.commit()
                run_id = cur.lastrowid
            conn.close()
        except Exception as e:
            logger.error(f"[Scheduler] Failed to insert run start: {e}")

        # Execute collection
        status = "success"
        records_collected = 0
        pages_crawled = 0
        duration = 0.0
        error_message = None

        try:
            collector = self._get_collector(platform)
            result = collector.collect(keyword, city, max_pages=max_pages)
            records_collected = len(result.records)
            pages_crawled = result.pages_crawled
            duration = result.duration_seconds
            if result.errors:
                error_message = "; ".join(result.errors[:5])  # first 5 errors
                if len(result.errors) > 5:
                    error_message += f" ... and {len(result.errors) - 5} more"
            logger.info(
                f"[Scheduler] {platform}/{keyword}/{city}: "
                f"{records_collected} records, {pages_crawled} pages, {duration:.1f}s"
            )
        except Exception as e:
            status = "failed"
            error_message = str(e)[:1000]
            logger.error(f"[Scheduler] {platform}/{keyword}/{city} failed: {e}")

        # Update run record
        finished_at = datetime.now()
        try:
            conn = pymysql.connect(
                host=settings.mysql_host, port=settings.mysql_port,
                user=settings.mysql_user, password=settings.mysql_password,
                database=settings.mysql_database, charset="utf8mb4",
            )
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
            logger.error(f"[Scheduler] Failed to update run {run_id}: {e}")

    def add_job(self, platform: str, keyword: str, city: str,
                interval_hours: int = 12, max_pages: int = 3) -> str:
        """Add a periodic collection job.

        Args:
            platform: Collector platform name (e.g. 'tencent', 'liepin')
            keyword: Search keyword
            city: Target city
            interval_hours: Hours between collection runs
            max_pages: Max pages per run

        Returns:
            Job ID string
        """
        job_id = f"{platform}_{keyword}_{city}"
        try:
            # Remove existing job with same ID if present
            try:
                self._scheduler.remove_job(job_id)
            except JobLookupError:
                pass

            self._scheduler.add_job(
                func=self._run_collection_job,
                trigger=IntervalTrigger(hours=interval_hours),
                args=(platform, keyword, city, max_pages),
                id=job_id,
                name=f"{platform}: {keyword}@{city}",
                replace_existing=True,
            )
            logger.info(
                f"[Scheduler] Added job {job_id}: every {interval_hours}h, "
                f"platform={platform}, keyword={keyword}, city={city}"
            )
        except Exception as e:
            logger.error(f"[Scheduler] Failed to add job {job_id}: {e}")
            raise
        return job_id

    def remove_job(self, job_id: str):
        """Remove a scheduled job by ID."""
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"[Scheduler] Removed job: {job_id}")
        except JobLookupError:
            logger.warning(f"[Scheduler] Job not found: {job_id}")

    def list_jobs(self) -> list[dict]:
        """List all scheduled jobs with their details."""
        jobs = []
        for job in self._scheduler.get_jobs():
            nrt = getattr(job, "next_run_time", None)
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": nrt.isoformat() if nrt else None,
                "trigger": str(job.trigger),
            })
        return jobs

    def start(self):
        """Start the scheduler."""
        self._scheduler.start()
        logger.info("[Scheduler] Started")

    def stop(self):
        """Shut down the scheduler."""
        self._scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Stopped")


# Module-level singleton
_scheduler_instance: Optional[CollectorScheduler] = None


def get_scheduler() -> CollectorScheduler:
    """Get or create the global scheduler singleton."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = CollectorScheduler()
    return _scheduler_instance
