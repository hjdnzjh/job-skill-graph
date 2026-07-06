"""Main ETL pipeline orchestrator.

Pipeline flow:
  Crawlers → Cleaner → Normalizer → Deduplicator → QualityScorer
  → MySQL (structured) + ES (full-text) + File (original)

This implements the architecture:
  Scrapy爬虫集群 → 数据清洗管道（去重/格式统一/质量评分）
  → MySQL结构化存储 + ES全文索引 + 文件系统存储原始文档
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

from config.settings import Settings
from config.schema import UnifiedJobSchema

try:
    from crawlers.spiders.recruitment import RecruitmentSpider
    from crawlers.spiders.enterprise import EnterpriseSpider
    from crawlers.spiders.policy import PolicySpider
    from crawlers.spiders.academic import AcademicSpider
    from crawlers.spiders.industry_report import IndustryReportSpider
    _CRAWLERS_AVAILABLE = True
except ImportError:
    _CRAWLERS_AVAILABLE = False
    RecruitmentSpider = None
    EnterpriseSpider = None
    PolicySpider = None
    AcademicSpider = None
    IndustryReportSpider = None

from etl.cleaner import DataCleaner
from etl.normalizer import Normalizer
from etl.deduplicator import Deduplicator
from etl.quality import QualityScorer

from storage.file_storage import FileStorage

# Optional: MySQL and ES (installed separately)
try:
    from storage.mysql_client import MySQLClient
except ImportError:
    MySQLClient = None

try:
    from storage.es_client import ElasticsearchClient
except ImportError:
    ElasticsearchClient = None

logger = logging.getLogger(__name__)


class DataPipeline:
    """Orchestrates the full data acquisition → storage pipeline."""

    def __init__(self, settings: Settings = None):
        self.settings = settings or Settings()
        self._setup_logging()

        # --- storage clients ---
        self.mysql = MySQLClient(self.settings) if MySQLClient else None
        self.es = ElasticsearchClient(self.settings) if ElasticsearchClient else None
        self.file_storage = FileStorage(self.settings)

        # --- ETL components ---
        self.cleaner = DataCleaner()
        self.normalizer = Normalizer()
        self.deduplicator = Deduplicator(
            similarity_threshold=self.settings.dedup_similarity_threshold
        )
        self.quality_scorer = QualityScorer(
            min_score=self.settings.quality_min_score
        )

        # --- crawlers ---
        if _CRAWLERS_AVAILABLE:
            self.spiders = {
                "recruitment": RecruitmentSpider(self.settings),
                "enterprise": EnterpriseSpider(self.settings),
                "policy": PolicySpider(self.settings),
                "academic": AcademicSpider(self.settings),
                "industry_report": IndustryReportSpider(self.settings),
            }
        else:
            self.spiders = {}

        self._stats: Dict[str, any] = {}

    # ------------------------------------------------------------------
    # Full pipeline execution
    # ------------------------------------------------------------------

    def run(
        self,
        keywords: List[str] = None,
        cities: List[str] = None,
        sources: List[str] = None,
        use_mysql: bool = False,
        use_es: bool = False,
    ) -> Dict[str, any]:
        """Execute the full data pipeline.

        Args:
            keywords: Search keywords for crawlers.
            cities: Target cities (recruitment only).
            sources: Which spider types to activate (default: all).
            use_mysql: Whether to write to MySQL.
            use_es: Whether to index into Elasticsearch.

        Returns:
            dict with pipeline statistics.
        """
        sources = sources or self.settings.enabled_sources
        start_time = time.time()

        # ------------------------------------------------------------------
        # Phase 1: Crawl
        # ------------------------------------------------------------------
        logger.info("=" * 60)
        logger.info("PHASE 1: Multi-source crawling")
        logger.info("=" * 60)

        all_records: List[UnifiedJobSchema] = []

        for source_name in sources:
            spider = self.spiders.get(source_name)
            if spider is None:
                logger.warning(f"Unknown source '{source_name}', skipping")
                continue

            logger.info(f"Starting crawler: {source_name}")
            t0 = time.time()

            try:
                if source_name == "recruitment":
                    records = spider.crawl(keywords=keywords, cities=cities)
                else:
                    records = spider.crawl(keywords=keywords)

                elapsed = time.time() - t0
                self._stats[f"crawl_{source_name}_count"] = len(records)
                self._stats[f"crawl_{source_name}_time"] = round(elapsed, 1)
                logger.info(f"  {source_name}: {len(records)} records, {elapsed:.1f}s")

                # Save raw records immediately (before ETL)
                if records:
                    self.file_storage.save_processed(
                        records, batch_tag=f"{source_name}_raw"
                    )

                all_records.extend(records)

            except Exception as exc:
                logger.error(f"Crawler {source_name} failed: {exc}", exc_info=True)

        self._stats["crawl_total"] = len(all_records)
        logger.info(f"Crawl phase complete: {len(all_records)} total records")

        if not all_records:
            logger.warning("No records collected. Pipeline stopped.")
            return self._stats

        # ------------------------------------------------------------------
        # Phase 2: ETL — Clean → Normalize → Dedup → Score
        # ------------------------------------------------------------------
        logger.info("=" * 60)
        logger.info("PHASE 2: ETL — Clean / Normalize / Dedup / Score")
        logger.info("=" * 60)

        # 2a. Clean
        t0 = time.time()
        records = self.cleaner.clean(all_records)
        self._stats["after_clean"] = len(records)
        logger.info(f"  2a. Clean: {len(all_records)} → {len(records)} ({time.time() - t0:.1f}s)")

        # 2b. Normalize
        t0 = time.time()
        records = self.normalizer.normalize(records)
        self._stats["after_normalize"] = len(records)
        logger.info(f"  2b. Normalize: {len(records)} records ({time.time() - t0:.1f}s)")

        # 2c. Dedup
        t0 = time.time()
        records = self.deduplicator.deduplicate(records)
        self._stats["after_dedup"] = len(records)
        logger.info(f"  2c. Dedup: → {len(records)} records ({time.time() - t0:.1f}s)")

        # 2d. Quality scoring
        t0 = time.time()
        records = self.quality_scorer.score_batch(records)
        self._stats["after_quality"] = len(records)
        quality_summary = QualityScorer.summary(records)
        self._stats["quality"] = quality_summary
        logger.info(f"  2d. Quality: {len(records)} passed (min={self.settings.quality_min_score})")
        logger.info(f"      Grade dist: {quality_summary['grade_distribution']}")
        logger.info(f"      Avg quality: {quality_summary['avg_quality']}")

        # ------------------------------------------------------------------
        # Phase 3: Storage — MySQL + ES + File
        # ------------------------------------------------------------------
        logger.info("=" * 60)
        logger.info("PHASE 3: Multi-tier storage")
        logger.info("=" * 60)

        # 3a. File storage (always — zero dependency)
        t0 = time.time()
        filepath = self.file_storage.save_processed(records, batch_tag="final")
        json_path = self.file_storage.save_processed_json(records)
        self._stats["file_storage_path"] = filepath
        self._stats["file_storage_json"] = json_path
        logger.info(f"  3a. File storage: {filepath}")

        # 3b. MySQL (optional — requires running MySQL instance)
        if use_mysql and self.mysql:
            t0 = time.time()
            try:
                self.mysql.init_db()
                inserted = self.mysql.insert_batch(records, batch_size=self.settings.batch_size)
                self._stats["mysql_inserted"] = inserted
                logger.info(f"  3b. MySQL: {inserted} records inserted ({(time.time() - t0):.1f}s)")
            except Exception as exc:
                logger.error(f"MySQL write failed: {exc}")
                self._stats["mysql_error"] = str(exc)
        else:
            logger.info("  3b. MySQL: skipped (use_mysql=False)")

        # 3c. Elasticsearch (optional — requires running ES instance)
        if use_es and self.es:
            t0 = time.time()
            try:
                self.es.create_index()
                indexed = self.es.index_batch(records, batch_size=self.settings.batch_size)
                self._stats["es_indexed"] = indexed
                logger.info(f"  3c. Elasticsearch: {indexed} documents indexed ({(time.time() - t0):.1f}s)")
            except Exception as exc:
                logger.error(f"ES write failed: {exc}")
                self._stats["es_error"] = str(exc)
        else:
            logger.info("  3c. Elasticsearch: skipped (use_es=False)")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        total_time = time.time() - start_time
        self._stats["pipeline_total_time"] = round(total_time, 1)
        self._stats["final_record_count"] = len(records)
        self._stats["completed_at"] = datetime.now().isoformat()

        logger.info("=" * 60)
        logger.info(f"PIPELINE COMPLETE — {len(records)} records in {total_time:.1f}s")
        logger.info(f"Stats: {json.dumps(self._stats, indent=2, ensure_ascii=False, default=str)}")
        logger.info("=" * 60)

        return self._stats

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _setup_logging(self):
        """Configure logging to both console and file."""
        log_dir = self.settings.log_dir
        os.makedirs(log_dir, exist_ok=True)

        log_format = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler = logging.FileHandler(
            f"{log_dir}/pipeline_{datetime.now().strftime('%Y%m%d')}.log",
            encoding="utf-8",
        )
        file_handler.setFormatter(log_format)
        file_handler.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_format)
        console_handler.setLevel(getattr(logging, self.settings.log_level.upper(), logging.INFO))

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.handlers.clear()
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    def get_stats(self) -> dict:
        return self._stats

    def print_summary(self):
        """Pretty-print pipeline summary to console."""
        s = self._stats
        print("\n" + "=" * 60)
        print("  多源异构数据采集与治理管道 — 执行摘要")
        print("=" * 60)
        print(f"  总爬取记录数:     {s.get('crawl_total', 0)}")
        print(f"  清洗后:           {s.get('after_clean', 0)}")
        print(f"  去重后:           {s.get('after_dedup', 0)}")
        print(f"  质量过滤后:       {s.get('after_quality', 0)}")
        print(f"  最终入库记录数:   {s.get('final_record_count', 0)}")

        if "quality" in s:
            q = s["quality"]
            print(f"  平均质量分:       {q.get('avg_quality', 0):.3f}")
            print(f"  质量等级分布:     {q.get('grade_distribution', {})}")

        print(f"  管道总耗时:       {s.get('pipeline_total_time', 0):.1f}s")
        print(f"  文件存储路径:     {s.get('file_storage_path', 'N/A')}")
        print("=" * 60 + "\n")
