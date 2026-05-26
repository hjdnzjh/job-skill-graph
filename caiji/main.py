"""Entry point for the data collection system.

Usage:
    python main.py                          # crawl + ETL + MySQL + file
    python main.py --demo                   # run with demo/mock data (no real crawl)
    python main.py --no-mysql               # skip MySQL, file only
    python main.py --keywords AI,Java,Go    # custom search keywords
    python main.py --min-quality 0.5        # quality score threshold
"""

import argparse
import logging
import sys

from config.settings import Settings
from pipeline import DataPipeline

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="数据采集系统 — 多源异构数据采集与治理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--keywords", type=str, default=None,
                        help="Comma-separated search keywords")
    parser.add_argument("--cities", type=str, default=None,
                        help="Comma-separated target cities")
    parser.add_argument("--sources", type=str, default=None,
                        help="Comma-separated source types (recruitment)")
    parser.add_argument("--demo", action="store_true", default=False,
                        help="Run with demo/mock data (no real HTTP requests)")
    parser.add_argument("--no-mysql", action="store_true", default=False,
                        help="Skip MySQL storage")
    parser.add_argument("--min-quality", type=float, default=0.3,
                        help="Minimum quality score threshold (default: 0.3)")
    parser.add_argument("--batch-size", type=int, default=500,
                        help="Batch size for storage operations")

    args = parser.parse_args()

    settings = Settings()
    settings.quality_min_score = args.min_quality
    settings.batch_size = args.batch_size

    keywords = args.keywords.split(",") if args.keywords else None
    cities = args.cities.split(",") if args.cities else None
    sources = args.sources.split(",") if args.sources else None

    pipeline = DataPipeline(settings)

    if args.demo:
        logger.info("Running in DEMO mode with synthetic data")
        from utils.demo_data import generate_demo_records
        records = generate_demo_records(count=200)
        logger.info(f"Generated {len(records)} demo records")

        # Run ETL
        records = pipeline.cleaner.clean(records)
        records = pipeline.normalizer.normalize(records)
        records = pipeline.deduplicator.deduplicate(records)
        records = pipeline.quality_scorer.score_batch(records)

        # File backup
        pipeline.file_storage.save_processed(records, batch_tag="demo_final")
        pipeline.file_storage.save_processed_json(records)

        # MySQL
        use_mysql = not args.no_mysql
        if use_mysql and pipeline.mysql:
            try:
                pipeline.mysql.init_db()
                inserted = pipeline.mysql.insert_batch(records, batch_size=settings.batch_size)
                logger.info(f"MySQL: {inserted} demo records inserted")
            except Exception as exc:
                logger.error(f"MySQL write failed: {exc}")

        from etl.quality import QualityScorer
        summary = QualityScorer.summary(records)
        print("\n=== Demo Run Summary ===")
        print(f"Records: {len(records)}")
        print(f"Avg quality: {summary['avg_quality']:.3f}")
        print(f"Grade distribution: {summary['grade_distribution']}")
        print(f"Files saved to: {settings.processed_data_dir}")
    else:
        stats = pipeline.run(
            keywords=keywords,
            cities=cities,
            sources=sources,
            use_mysql=not args.no_mysql,
        )
        pipeline.print_summary()


if __name__ == "__main__":
    main()
