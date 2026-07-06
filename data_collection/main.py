"""Entry point for the multi-source data collection & governance system.

Usage:
    python main.py                          # crawl + ETL, save to file only
    python main.py --mysql                  # also write to MySQL
    python main.py --es                     # also index into Elasticsearch
    python main.py --keywords AI,Java,Go    # custom search keywords
    python main.py --demo                   # run with demo/mock data (no real crawl)
"""

import argparse
import logging
import sys

from config.settings import Settings
from pipeline import DataPipeline

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="多源异构数据采集与治理系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--keywords", type=str, default=None,
                        help="Comma-separated search keywords")
    parser.add_argument("--cities", type=str, default=None,
                        help="Comma-separated target cities")
    parser.add_argument("--sources", type=str, default=None,
                        help="Comma-separated source types (recruitment,enterprise,policy,academic,industry_report)")
    parser.add_argument("--mysql", action="store_true", default=False,
                        help="Enable MySQL storage")
    parser.add_argument("--es", action="store_true", default=False,
                        help="Enable Elasticsearch indexing")
    parser.add_argument("--demo", action="store_true", default=False,
                        help="Run with demo/mock data (no real HTTP requests)")
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
        # Use mock data generator instead of real crawlers
        logger.info("Running in DEMO mode with synthetic data")
        from utils.demo_data import generate_demo_records
        records = generate_demo_records(count=200)
        logger.info(f"Generated {len(records)} demo records")

        # Run ETL phases directly
        records = pipeline.cleaner.clean(records)
        records = pipeline.normalizer.normalize(records)
        records = pipeline.deduplicator.deduplicate(records)
        records = pipeline.quality_scorer.score_batch(records)

        # Save
        pipeline.file_storage.save_processed(records, batch_tag="demo_final")
        pipeline.file_storage.save_processed_json(records)

        # Summary
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
            use_mysql=args.mysql,
            use_es=args.es,
        )
        pipeline.print_summary()


if __name__ == "__main__":
    main()
