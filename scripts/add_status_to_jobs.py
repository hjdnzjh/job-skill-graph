"""
One-time migration: add 'status' property to existing Neo4j nodes.

Usage:
    python scripts/add_status_to_jobs.py              # apply changes
    python scripts/add_status_to_jobs.py --dry-run    # preview only, no changes

- Job nodes -> status: "active" (already crawled/published data)
- EmergingJob nodes -> status: "pending" (awaiting review)
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "caiji"))

from config.settings import Settings
from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Add status property to Neo4j nodes")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying")
    args = parser.parse_args()

    settings = Settings()
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    driver.verify_connectivity()
    logger.info(f"Connected to Neo4j at {settings.neo4j_uri}")

    with driver.session(database=settings.neo4j_database) as session:
        job_null = session.run(
            "MATCH (j:Job) WHERE j.status IS NULL RETURN count(j) AS c"
        ).single()["c"]
        ej_null = session.run(
            "MATCH (e:EmergingJob) WHERE e.status IS NULL RETURN count(e) AS c"
        ).single()["c"]
        total = job_null + ej_null

        logger.info(f"Nodes needing status: {job_null} Job + {ej_null} EmergingJob = {total}")

        if total == 0:
            logger.info("All nodes already have status set. Nothing to do.")
            driver.close()
            return

        if args.dry_run:
            logger.info("DRY RUN - no changes applied. Would update:")
            if job_null:
                logger.info(f"  SET {job_null} Job nodes -> status='active'")
            if ej_null:
                logger.info(f"  SET {ej_null} EmergingJob nodes -> status='pending'")
            driver.close()
            return

        if job_null:
            result = session.run(
                "MATCH (j:Job) WHERE j.status IS NULL "
                "SET j.status = 'active' "
                "RETURN count(j) AS updated"
            ).single()
            logger.info(f"Job nodes updated: {result['updated']}")

        if ej_null:
            result = session.run(
                "MATCH (e:EmergingJob) WHERE e.status IS NULL "
                "SET e.status = 'pending' "
                "RETURN count(e) AS updated"
            ).single()
            logger.info(f"EmergingJob nodes updated: {result['updated']}")

    driver.close()


if __name__ == "__main__":
    main()
