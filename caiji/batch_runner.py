"""Continuous batch crawler — runs keyword/city combinations indefinitely.

Each round picks a keyword group × city tier, runs the pipeline,
saves to MySQL, and moves to the next. Designed for long-running
unattended operation with built-in anti-detection delays.
"""

import logging
import random
import sys
import time
from datetime import datetime

from config.settings import Settings
from pipeline import DataPipeline

logger = logging.getLogger(__name__)

# Import keyword groups from the spider
from crawlers.recruitment import KEYWORD_GROUPS, CITY_GROUPS


def run_batch(settings, keywords, cities, pages, batch_id):
    """Run a single crawl+ETL+storage batch."""
    pipeline = DataPipeline(settings)

    logger.info(f"=== BATCH {batch_id}: {len(keywords)}kw × {len(cities)}cities ===")

    stats = pipeline.run(
        keywords=keywords,
        cities=cities,
        sources=["recruitment"],
        use_mysql=True,
        pages=pages,
    )

    return stats.get("final_record_count", 0), stats.get("mysql_inserted", 0)


def main():
    settings = Settings()

    # track cumulative stats
    total_crawled = 0
    total_stored = 0
    round_num = 0

    # keyword groups to cycle through (in order)
    kw_group_names = [
        "backend", "frontend", "data_ai", "bigdata", "devops",
        "mobile", "testing", "product_design", "security",
        "blockchain", "game", "embedded", "management",
    ]

    # city tiers to cycle through
    city_tiers = ["tier1", "tier2", "tier3"]

    logger.info("=" * 60)
    logger.info("CONTINUOUS BATCH CRAWLER STARTED")
    logger.info(f"Keyword groups: {len(kw_group_names)}")
    logger.info(f"City tiers: {len(city_tiers)}")
    logger.info(f"Total combos: {len(kw_group_names) * len(city_tiers)}")
    logger.info("=" * 60)

    try:
        while True:
            round_num += 1

            # Pick keyword group (rotate)
            kw_idx = (round_num - 1) % len(kw_group_names)
            kw_group = kw_group_names[kw_idx]
            keywords = KEYWORD_GROUPS.get(kw_group, ["Java开发"])

            # Pick city tier (rotate)
            city_idx = (round_num - 1) % len(city_tiers)
            city_tier = city_tiers[city_idx]
            cities = CITY_GROUPS.get(city_tier, ["北京"])

            # Reduce pages per query for tier2/3 cities to be faster
            pages = 2 if city_tier == "tier3" else 3

            logger.info(f"\n{'=' * 60}")
            logger.info(f"ROUND {round_num}: group={kw_group} ({len(keywords)}kw)"
                        f" tier={city_tier} ({len(cities)}cities) pages={pages}")
            logger.info(f"Keywords: {', '.join(keywords[:5])}{'...' if len(keywords) > 5 else ''}")
            logger.info(f"Cities: {', '.join(cities)}")
            logger.info(f"{'=' * 60}")

            try:
                new_records, mysql_inserted = run_batch(settings, keywords, cities,
                                                         pages, round_num)

                total_crawled += new_records
                total_stored += mysql_inserted

                logger.info(f"ROUND {round_num} DONE: +{new_records} final, "
                            f"+{mysql_inserted} MySQL | "
                            f"Total: {total_crawled} final / {total_stored} stored")

            except Exception as exc:
                logger.error(f"ROUND {round_num} FAILED: {exc}", exc_info=True)

            # Inter-round delay (shorter for speed, with jitter)
            delay = random.randint(30, 60)
            logger.info(f"Waiting {delay}s ({delay/60:.0f}min) before next round...")
            time.sleep(delay)

    except KeyboardInterrupt:
        logger.info("\nBatch runner stopped by user")
        logger.info(f"Final: {total_crawled} records / {total_stored} MySQL / {round_num} rounds")
        print(f"\n=== Batch Runner Stopped ===")
        print(f"Rounds completed: {round_num}")
        print(f"Total records: {total_crawled}")
        print(f"MySQL stored: {total_stored}")


if __name__ == "__main__":
    main()
